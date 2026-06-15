#!/usr/bin/env python3
"""
audit_ballot.py — Ekklesia ballot auditor (on-chain only)

Independently verifies the cryptographic record of an Ekklesia ballot from
nothing but Cardano L1 + IPFS. The Ekklesia backend and Hydra middleware
need not be running. The voting authority's admin wallet and a Cardano
data provider are the only things you need.

What the script verifies, end-to-end:

    Cardano L1 (Blockfrost)
      |
      +-- (600) ballot-definition token UTxO at the admin wallet
      |     inline datum -> ekklesia.merkleRoot, ballotCid, etc.
      |
      |   --[blake2b-256 over question leaves, lerna-labs/hydra-proof]--
      |
      +-- IPFS-pinned ballot JSON (via ballotCid)
      |     questions[] -> per-question contentHash
      |
      +-- (601) ballot-instance token UTxO at the admin wallet
      |     inline datum -> resultsHash, evidenceCid, evidenceMerkleRoot
      |
      |   --[blake2b-256 over results.json bytes]--
      |   --[merkle root over per-voter voteHashes]--
      |
      +-- IPFS-pinned evidence directory (via evidenceCid)
            results.json          -> matches resultsHash
            proof-package.json    -> rootHex matches evidenceMerkleRoot
            vote-{voter}-vN.json  -> blake2b-256 matches each voteHash leaf
              ekklesia.witnesses[].coseSign1Hex -> ed25519 verifies & ASCII
                                                  payload == merkleRoot
              ekklesia.witnesses[].coseKeyHex   -> blake2b-224(pubkey)
                                                  matches voterId credential
                                                  (or calidus key for SPOs)
            history/{voterId}.json -> per-voter chain: versions strictly
                                      increase, prevTxHash == prior txHash,
                                      last entry's voteHash matches the
                                      committed leaf

    (601) UTxO lineage on L1
      tx that created the (601) UTxO -> walked back through any rebalance
                                        hops; every predecessor must carry
                                        the SAME inline datum. The walk
                                        ends at the original Hydra fanout
                                        tx (input lives at a Hydra script
                                        address, not the admin wallet).

    Voting-window enforcement
      every history[i].timestamp falls inside [windowOpen, windowClose]
      from the (600) datum.

    Independent re-tally
      per-role per-option counts derived from each voter's signed answers
      are byte-equal to the published `results.json` tally — full coverage
      of every Ekklesia method: binary, single-choice, multi-choice,
      range/scale (value-distribution histograms), ranked (first-pref
      counts + pairwise matrix), weighted/budget (totalPoints + voterCount),
      and likert (rater count + per-rating distribution).

Any single mismatch in this chain breaks the audit and signals tampering.
Rebalance hops (admin -> admin, same datum) are reported as informational
notes, not failures, since they're a normal operational pattern when
minUTxO requirements change.

Usage:
    python3 audit_ballot.py \\
        --admin addr_test1vz...lj6 \\
        --blockfrost-key preprodXXXXXXXX \\
        [--network preprod|mainnet|preview] \\
        [--ipfs-gateway https://ipfs.io/ipfs] \\
        [--ballot-fingerprint <hex>] \\
        [--voter <bech32-or-tokenname>] \\
        [--voter-receipt PATH]   (requires --voter; portable inclusion proof) \\
        [--export PATH]          (verified ballot + per-voter votes for weighting) \\
        [--skip-signatures] [--skip-history] [--skip-lineage] [--skip-retally]

Dependencies:
    pip install cbor2 cryptography bech32

cbor2 is required. cryptography + bech32 are required only for the
deeper signature/history checks; the script falls back to skipping
those checks (with a clear note) if either is missing.

License: MIT  (this script is part of the Ekklesia public docs)
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from hashlib import blake2b
from typing import Any

try:
    import cbor2
except ImportError:
    sys.stderr.write("Missing dependency: cbor2.  Install with: pip install cbor2\n")
    sys.exit(2)

# Optional deps — used by the deeper checks. If absent, those steps will
# emit a [SKIP] note and continue. Required-for-correctness steps still run.
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    HAVE_ED25519 = True
except ImportError:
    HAVE_ED25519 = False

try:
    import bech32 as _bech32
    HAVE_BECH32 = True
except ImportError:
    HAVE_BECH32 = False


# --- Constants from hydra/src/types.ts ---------------------------------------

# CIP-67 4-byte prefixes that identify the two ballot tokens.
BALLOT_DEFINITION_PREFIX = "00258a50"   # (600) reference token, holds the immutable commitment
BALLOT_INSTANCE_PREFIX   = "00259a20"   # (601) state token, carries settlement results

# Per-network Blockfrost base URL.
BLOCKFROST_BASE = {
    "preprod": "https://cardano-preprod.blockfrost.io/api/v0",
    "mainnet": "https://cardano-mainnet.blockfrost.io/api/v0",
    "preview": "https://cardano-preview.blockfrost.io/api/v0",
}

DEFAULT_IPFS_GATEWAY = "https://ipfs.io/ipfs"

# Hydra plutus-script address prefixes (mainnet/testnet) — any input UTxO
# whose address starts with these is a script address, used here as a
# heuristic to distinguish a Hydra fanout from an admin-wallet rebalance.
SCRIPT_ADDR_PREFIXES = ("addr_test1w", "addr1w")


# --- Tiny helpers ------------------------------------------------------------

def blake2b_256(data: bytes) -> bytes:
    return blake2b(data, digest_size=32).digest()

def blake2b_224(data: bytes) -> bytes:
    return blake2b(data, digest_size=28).digest()

def hexd(b: bytes) -> str:
    return b.hex()

class AuditError(Exception):
    pass


# --- Bech32 (Cardano addr/stake/drep/pool/calidus) --------------------------

def bech32_decode(s: str) -> tuple:
    """Decode a Cardano bech32 string to (hrp, raw_bytes).

    The PyPI `bech32` module hard-codes BIP-173's 90-character limit,
    which is fine for every voterId encoding we touch
    (drep/pool/stake/cc_*/calidus all stay well under 90 chars). Full
    Cardano base addresses (addr1.../addr_test1...) can exceed the
    limit; we don't decode those here, so the cap doesn't bite.
    """
    if not HAVE_BECH32:
        raise AuditError("bech32 package not installed (pip install bech32)")
    hrp, words = _bech32.bech32_decode(s)
    if hrp is None or words is None:
        raise AuditError(f"invalid bech32 string: {s}")
    raw = _bech32.convertbits(words, 5, 8, False)
    if raw is None:
        raise AuditError(f"bech32 convertbits failed: {s}")
    return hrp, bytes(raw)


# --- COSE_Sign1 (CIP-08 / CIP-30) verification ------------------------------

def verify_cose_witness(witness: dict, signed_payload_obj: dict) -> dict:
    """Verify one COSE witness against a canonical signedPayload.

    Walks the same algorithm as the production verifier
    (@lerna-labs/hydra-sdk/utils/verify-signature.js):

        1. Parse COSE_Sign1 = [protected_bstr, unprotected, payload, sig]
        2. Build Sig_structure = ["Signature1", protected_bstr, b"", payload]
        3. ed25519.verify(coseKey.pubkey, CBOR(Sig_structure), sig)
        4. payload (ASCII-decoded) must equal merkleRoot, where
           merkleRoot = blake2b_256(JSON.stringify(signedPayload)) hex.

    Returns a dict:
      - ok:         True | False | None ('None' = could-not-verify because
                    the cryptography package is missing)
      - error:      str | None
      - pubkey_hex: 32-byte ed25519 public key hex
      - keyhash:    blake2b_224(pubkey) hex (Cardano credential key hash)
    """
    try:
        cose_sign1 = cbor2.loads(bytes.fromhex(witness["coseSign1Hex"]))
        cose_key = cbor2.loads(bytes.fromhex(witness["coseKeyHex"]))
    except Exception as e:
        return {"ok": False, "error": f"COSE parse failure: {e}"}
    if not isinstance(cose_sign1, list) or len(cose_sign1) != 4:
        return {"ok": False, "error": "COSE_Sign1 is not a 4-element CBOR array"}
    protected_bstr, _unprotected, payload, signature = cose_sign1
    pubkey = cose_key.get(-2) if isinstance(cose_key, dict) else None
    if not isinstance(pubkey, (bytes, bytearray)) or len(pubkey) != 32:
        return {"ok": False, "error": "COSE_Key has no valid 32-byte ed25519 pubkey at label -2"}
    keyhash = blake2b_224(bytes(pubkey)).hex()

    sp_bytes = json.dumps(signed_payload_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    expected_mr = blake2b_256(sp_bytes).hex()
    try:
        payload_ascii = bytes(payload).decode("ascii")
    except UnicodeDecodeError:
        return {"ok": False, "error": "COSE payload is not ASCII", "pubkey_hex": bytes(pubkey).hex(), "keyhash": keyhash}
    if payload_ascii != expected_mr:
        return {
            "ok": False,
            "error": f"COSE payload != merkleRoot (got {payload_ascii[:16]}..., expected {expected_mr[:16]}...)",
            "pubkey_hex": bytes(pubkey).hex(),
            "keyhash": keyhash,
        }

    if not HAVE_ED25519:
        return {"ok": None, "error": "cryptography package not installed", "pubkey_hex": bytes(pubkey).hex(), "keyhash": keyhash}
    sig_structure_cbor = cbor2.dumps(["Signature1", protected_bstr, b"", payload])
    try:
        Ed25519PublicKey.from_public_bytes(bytes(pubkey)).verify(bytes(signature), sig_structure_cbor)
    except InvalidSignature:
        return {"ok": False, "error": "ed25519 signature verification failed", "pubkey_hex": bytes(pubkey).hex(), "keyhash": keyhash}
    return {"ok": True, "error": None, "pubkey_hex": bytes(pubkey).hex(), "keyhash": keyhash}


def voter_id_to_token_name(voter_id: str) -> str:
    """Derive the on-chain voter token name from a bech32 voterId.

    The Hydra middleware's convention (hydra/src/types.ts):

        token_name = HRP_byte || blake2b_224(<bech32-decoded raw bytes>)

    where HRP_byte is the CIP-129 header byte for credential types that
    have one (drep/cc_*/stake), or a fixed Ekklesia-defined byte for
    types whose bech32 encodes only a 28-byte hash (pool: 0x06, calidus
    ports through to 0x06 via the pool credential).
    """
    hrp, raw = bech32_decode(voter_id)
    if hrp == "pool":
        hrp_byte = 0x06
    elif len(raw) == 29:
        # CIP-129: first byte is the header
        hrp_byte = raw[0]
    else:
        raise AuditError(
            f"unrecognised bech32 shape for {voter_id!r} "
            f"(hrp={hrp}, {len(raw)} bytes)"
        )
    return f"{hrp_byte:02x}" + blake2b_224(raw).hex()


def resolve_voter_filter(voter_arg: str, voter_files: list) -> str:
    """Resolve a user-provided --voter argument (bech32 or hex tokenname)
    against the ballot's actual voter list. Returns the matching token
    name, or raises AuditError listing the closest matches."""
    candidate = voter_arg.strip().lower()
    available = {f["name"] for f in voter_files}

    # Direct hex match
    if all(c in "0123456789abcdef" for c in candidate) and len(candidate) in (56, 58):
        if candidate in available:
            return candidate
        raise AuditError(
            f"no voter with token name {candidate} in this ballot "
            f"({len(available)} voters total)"
        )
    # Bech32 → derive token name
    try:
        tn = voter_id_to_token_name(voter_arg.strip())
    except AuditError as e:
        raise AuditError(f"could not parse --voter {voter_arg!r}: {e}")
    if tn in available:
        return tn
    raise AuditError(
        f"voterId {voter_arg!r} (derived token name {tn}) is not in this ballot's "
        f"{len(available)} voters"
    )


def keyhash_matches_voter(keyhash_hex: str, voter_id: str, calidus_id: str = None) -> tuple:
    """Confirm a witness pubkey hash is consistent with the claimed voterId.

    For non-pool credentials (drep/stake/cc) the bech32 decodes to
    1 header byte + 28 cred bytes; the cred bytes must equal the keyhash.

    For pool voters with no calidus declaration, the bech32 decodes to
    28 raw bytes which must equal the keyhash directly.

    For pool voters WITH a calidus declaration, the keyhash matches the
    calidus key hash (calidusId bech32 decoded skipping its 1-byte
    header). Confirming the calidus key is registered to the pool on L1
    is a separate certificate-lookup check, out of scope for this
    pure-on-chain script — we surface that as an informational note.

    Returns (ok: bool, note: str).
    """
    try:
        hrp, raw = bech32_decode(voter_id)
    except AuditError as e:
        return False, str(e)
    if hrp == "pool":
        if raw.hex() == keyhash_hex:
            return True, "matched pool key directly"
        if calidus_id:
            try:
                _, cal_raw = bech32_decode(calidus_id)
            except AuditError as e:
                return False, f"could not decode calidusId: {e}"
            cal_keyhash = cal_raw[1:].hex() if len(cal_raw) == 29 else cal_raw.hex()
            if cal_keyhash == keyhash_hex:
                return True, "matched calidus key (pool delegation requires L1 cert lookup to verify, see notes)"
            return False, f"calidus mismatch: cred {cal_keyhash[:12]}... vs pubkey hash {keyhash_hex[:12]}..."
        return False, f"pool key {raw.hex()[:12]}... vs pubkey hash {keyhash_hex[:12]}..."
    if len(raw) == 29:
        if raw[1:].hex() == keyhash_hex:
            return True, f"matched {hrp} key credential"
        return False, f"{hrp} cred {raw[1:].hex()[:12]}... vs pubkey hash {keyhash_hex[:12]}..."
    if raw.hex() == keyhash_hex:
        return True, f"matched {hrp} hash"
    return False, f"{hrp} hash {raw.hex()[:12]}... vs pubkey hash {keyhash_hex[:12]}..."


# --- Step printer ------------------------------------------------------------

class Report:
    """Accumulates pass/fail markers and prints a human-readable trace."""
    def __init__(self):
        self.failures = 0
        self.warnings = 0
        self.checks = 0
    def header(self, text: str) -> None:
        print()
        print("=" * 78)
        print(text)
        print("=" * 78)
    def step(self, text: str) -> None:
        print()
        print(f"--- {text}")
    def ok(self, text: str) -> None:
        self.checks += 1
        print(f"  [OK]   {text}")
    def fail(self, text: str) -> None:
        self.checks += 1
        self.failures += 1
        print(f"  [FAIL] {text}")
    def warn(self, text: str) -> None:
        self.warnings += 1
        print(f"  [WARN] {text}")
    def info(self, text: str) -> None:
        print(f"         {text}")
    def summary(self) -> int:
        print()
        print("=" * 78)
        warn_tag = f", {self.warnings} warning{'' if self.warnings == 1 else 's'}" if self.warnings else ""
        if self.failures == 0:
            print(f"AUDIT PASSED  ({self.checks} checks, 0 failures{warn_tag})")
            return 0
        print(f"AUDIT FAILED  ({self.checks} checks, {self.failures} failures{warn_tag})")
        return 1


# --- Cardano L1 access (Blockfrost) -----------------------------------------

class Blockfrost:
    def __init__(self, base: str, project_id: str):
        self.base = base.rstrip("/")
        self.project_id = project_id
    def _get(self, path: str) -> Any:
        url = f"{self.base}{path}"
        req = urllib.request.Request(url, headers={"project_id": self.project_id})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise AuditError(f"Blockfrost {e.code} at {path}: {e.read()[:300]!r}")
    def address_utxos(self, addr: str) -> list:
        out = []
        page = 1
        while True:
            chunk = self._get(f"/addresses/{addr}/utxos?count=100&page={page}")
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return out
    def tx_utxos(self, tx_hash: str) -> dict:
        """Return inputs/outputs for a transaction, used to walk (601)
        UTxO lineage back to the Hydra fanout."""
        return self._get(f"/txs/{tx_hash}/utxos")


# --- IPFS access -------------------------------------------------------------

USER_AGENT = "ekklesia-ballot-auditor/1.0"

def ipfs_get(gateway: str, cid_or_path: str) -> bytes:
    url = f"{gateway.rstrip('/')}/{cid_or_path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise AuditError(f"IPFS gateway {e.code} fetching {url}")
    except urllib.error.URLError as e:
        raise AuditError(f"IPFS gateway error fetching {url}: {e}")


# --- Datum decoding ----------------------------------------------------------

def decode_definition_datum(datum_hex: str) -> dict:
    """Decode the (600) ballot-definition inline datum.

    Plutus shape: Constr 0 [ [title, namespace, authority, merkleRoot,
                              ballotCid, qCount, windowOpen, windowClose,
                              endEpoch], schemaVersion ]
    """
    obj = cbor2.loads(bytes.fromhex(datum_hex))
    if not isinstance(obj, cbor2.CBORTag) or obj.tag != 121:
        raise AuditError("(600) datum is not a Plutus Constr 0")
    inner, schema_version = obj.value
    if len(inner) != 9:
        raise AuditError(f"(600) datum inner has {len(inner)} fields, expected 9")
    return {
        "title":         inner[0].decode("utf-8"),
        "namespace":     inner[1].decode("utf-8"),
        "authority":     inner[2].decode("utf-8"),
        "merkleRoot":    inner[3].hex(),
        "ballotCid":     inner[4].decode("utf-8"),
        "questionCount": int(inner[5]),
        "windowOpen":    inner[6].decode("utf-8"),
        "windowClose":   inner[7].decode("utf-8"),
        "endEpoch":      int(inner[8]),
        "schemaVersion": int(schema_version),
    }

def decode_instance_datum(datum_hex: str) -> dict:
    """Decode the (601) ballot-instance settlement inline datum.

    Plutus shape: Constr 0 [ [ballotId, resultsHash, evidenceCid, merkleRoot],
                             schemaVersion ]
    Pre-finalize the inner list may be all empty bytes; this audit only
    runs on a settled ballot.
    """
    obj = cbor2.loads(bytes.fromhex(datum_hex))
    if not isinstance(obj, cbor2.CBORTag) or obj.tag != 121:
        raise AuditError("(601) datum is not a Plutus Constr 0")
    inner, schema_version = obj.value
    if len(inner) != 4:
        raise AuditError(f"(601) datum inner has {len(inner)} fields, expected 4")
    return {
        "ballotId":           inner[0].hex(),
        "resultsHash":        inner[1].hex(),
        "evidenceCid":        inner[2].decode("utf-8") if isinstance(inner[2], bytes) else inner[2],
        "evidenceMerkleRoot": inner[3].hex(),
        "schemaVersion":      int(schema_version),
    }


# --- Merkle (lerna-labs/hydra-proof, mode='content+path') -------------------

def leaf_hash(name: str, content_hash_hex: str) -> bytes:
    return blake2b_256(b"\x00" + bytes.fromhex(content_hash_hex) + name.encode("utf-8"))

def parent_hash(a: bytes, b: bytes) -> bytes:
    # Lex-sort siblings by hex so the tree is deterministic regardless of order.
    L, R = (a, b) if a.hex() < b.hex() else (b, a)
    return blake2b_256(b"\x01" + L + R)

def build_root(leaves: list) -> bytes:
    if not leaves:
        return b""
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(parent_hash(left, right))
        level = nxt
    return level[0]

def verify_inclusion(name: str, content_hash_hex: str, proof: list, expected_root_hex: str) -> bool:
    node = leaf_hash(name, content_hash_hex)
    for step in proof:
        node = parent_hash(node, bytes.fromhex(step["siblingHex"]))
    return node.hex() == expected_root_hex.lower()


# --- Ballot discovery --------------------------------------------------------

def find_ballot_pairs(utxos: list) -> dict:
    """Walk the admin wallet's UTxOs and collect (600)/(601) token pairs by
    fingerprint. Returns {fingerprint: {definition: utxo, instance: utxo}}."""
    pairs: dict = {}
    for u in utxos:
        for asset in u.get("amount", []):
            unit = asset.get("unit", "")
            if unit == "lovelace":
                continue
            asset_name = unit[56:]   # asset_name = unit minus 28-byte policyId
            if asset_name.startswith(BALLOT_DEFINITION_PREFIX):
                fp = asset_name[len(BALLOT_DEFINITION_PREFIX):]
                pairs.setdefault(fp, {})["definition"] = u
                pairs[fp]["policyId"] = unit[:56]
            elif asset_name.startswith(BALLOT_INSTANCE_PREFIX):
                fp = asset_name[len(BALLOT_INSTANCE_PREFIX):]
                pairs.setdefault(fp, {})["instance"] = u
                pairs[fp]["policyId"] = unit[:56]
    return pairs


# --- Deeper audit phases -----------------------------------------------------

def verify_signatures_phase(report: Report, voter_files: list, matched_evidence: dict,
                            ballot_id_hex: str, export_voters: list = None) -> None:
    """Step 7: for each voter, decode every COSE witness in the latest
    evidence file and confirm:
      - ed25519 signature verifies against CBOR(Sig_structure)
      - COSE payload (ASCII) equals merkleRoot of canonical signedPayload
      - signedPayload.ballotId matches the on-chain ballot id
      - signedPayload.nonce matches the matched evidence version
      - blake2b_224(pubkey) matches the voterId credential (or the calidus
        key when a calidus declaration is present on a pool voter)
    """
    report.step("Step 7: per-voter COSE_Sign1 signatures verify")
    if not HAVE_ED25519 or not HAVE_BECH32:
        missing = []
        if not HAVE_ED25519: missing.append("cryptography")
        if not HAVE_BECH32: missing.append("bech32")
        report.fail(
            f"cannot verify signatures — install required deps "
            f"(`pip install {' '.join(missing)}`) or re-run with --skip-signatures "
            f"to record an audit that intentionally skipped this step"
        )
        return
    for f in voter_files:
        voter = f["name"]
        m = matched_evidence.get(voter)
        if not m:
            report.fail(f"voter {voter}: no evidence cached from step 6")
            continue
        ev = m["evidence"]
        ekklesia = ev.get("ekklesia") or {}
        signed_payload = ekklesia.get("signedPayload") or {}
        witnesses = ekklesia.get("witnesses") or []
        if not witnesses:
            report.fail(f"voter {voter}: no COSE witnesses in evidence")
            continue
        if signed_payload.get("ballotId") != ballot_id_hex:
            report.fail(f"voter {voter}: signedPayload.ballotId {signed_payload.get('ballotId')} != on-chain {ballot_id_hex}")
            continue
        if int(signed_payload.get("nonce", -1)) != m["version"]:
            report.fail(f"voter {voter}: signedPayload.nonce {signed_payload.get('nonce')} != evidence version {m['version']}")
            continue

        voter_id = ekklesia.get("voterId") or ""
        cal_id = (ekklesia.get("calidusDeclaration") or {}).get("calidusId")
        all_ok = True
        keyhashes = []
        for w in witnesses:
            r = verify_cose_witness(w, signed_payload)
            if r["ok"] is None:
                report.fail(f"voter {voter}: {r.get('error')} (cryptography missing)")
                all_ok = False
                break
            if r["ok"] is False:
                report.fail(f"voter {voter}: {r.get('error')}")
                all_ok = False
                break
            cred_ok, note = keyhash_matches_voter(r["keyhash"], voter_id, cal_id)
            if not cred_ok:
                report.fail(f"voter {voter}: signature ed25519 valid, but pubkey hash {r['keyhash'][:16]}... not authorised — {note}")
                all_ok = False
                break
            keyhashes.append((r["keyhash"], note))
        if all_ok:
            tag = " (calidus)" if cal_id else ""
            extra = ""
            if len(witnesses) > 1:
                extra = f" {len(witnesses)} witnesses"
            note = keyhashes[0][1] if keyhashes else ""
            report.ok(f"voter {voter}{tag}: ed25519+message+credential verified{extra}  — {note}")
            if export_voters is not None:
                for r in export_voters:
                    if r["tokenName"] == voter and keyhashes:
                        r["credentialKeyHash"] = keyhashes[0][0]
                        r["witnessCount"] = len(witnesses)


def verify_history_phase(report: Report, voter_files: list, matched_evidence: dict,
                         gateway: str, evidence_cid: str, export_voters: list = None,
                         window_open_iso: str = None, window_close_iso: str = None) -> None:
    """Step 8: fetch each voter's history/{voterId}.json and confirm:
      - versions strictly ascend from 1 with no gaps
      - prevTxHash on entry i equals txHash on entry i-1
      - the last entry's voteHash matches the committed leaf in proof-package
      - every entry's `timestamp` (ms epoch) lies within the on-chain
        voting window [windowOpen, windowClose] from the (600) datum
    """
    report.step("Step 8: per-voter vote-history chain + voting-window enforcement")
    open_ms = parse_iso_to_ms(window_open_iso) if window_open_iso else None
    close_ms = parse_iso_to_ms(window_close_iso) if window_close_iso else None
    if open_ms is None or close_ms is None:
        print(f"           [NOTE] could not parse on-chain voting window ({window_open_iso!r} -> {window_close_iso!r}) — skipping per-vote timestamp check")
    for f in voter_files:
        voter = f["name"]
        m = matched_evidence.get(voter)
        if not m:
            report.fail(f"voter {voter}: no evidence cached from step 6")
            continue
        voter_id = (m["evidence"].get("ekklesia") or {}).get("voterId")
        if not voter_id:
            report.fail(f"voter {voter}: evidence missing ekklesia.voterId")
            continue
        try:
            hist_bytes = ipfs_get(gateway, f"{evidence_cid}/history/{voter_id}.json")
        except AuditError as e:
            report.fail(f"voter {voter}: history/{voter_id}.json not pinned ({e})")
            continue
        try:
            history = json.loads(hist_bytes)
        except json.JSONDecodeError as e:
            report.fail(f"voter {voter}: history file malformed: {e}")
            continue
        if not isinstance(history, list) or not history:
            report.fail(f"voter {voter}: history is empty or not an array")
            continue
        prev_tx = None
        ok = True
        for i, entry in enumerate(history):
            v = entry.get("version")
            if v != i + 1:
                report.fail(f"voter {voter}: history[{i}] version={v}, expected {i+1}")
                ok = False; break
            if i == 0:
                if entry.get("prevTxHash"):
                    report.fail(f"voter {voter}: history[0] should have no prevTxHash, got {entry.get('prevTxHash')}")
                    ok = False; break
            else:
                if entry.get("prevTxHash") != prev_tx:
                    report.fail(f"voter {voter}: history[{i}] prevTxHash chain broken")
                    ok = False; break
            tx_hash = entry.get("txHash")
            if not tx_hash:
                report.fail(f"voter {voter}: history[{i}] missing txHash")
                ok = False; break
            prev_tx = tx_hash
        if not ok:
            continue
        last_vh = history[-1].get("voteHash")
        if last_vh != f["contentHashHex"]:
            report.fail(f"voter {voter}: last history voteHash {last_vh[:16]}... != committed leaf {f['contentHashHex'][:16]}...")
            continue
        # Voting-window enforcement
        window_warned = False
        if open_ms is not None and close_ms is not None:
            wok, werr, wwarn = verify_window_for_history(history, open_ms, close_ms)
            if not wok:
                report.fail(f"voter {voter}: {werr} (window: {window_open_iso} -> {window_close_iso})")
                continue
            if wwarn:
                report.warn(f"voter {voter}: {wwarn}")
                window_warned = True

        n = len(history)
        if open_ms is None:
            window_tag = ""
        elif window_warned:
            window_tag = " + within-window (partial: some timestamps unrecorded)"
        else:
            window_tag = " + within-window"
        report.ok(f"voter {voter}: history chain intact ({n} entr{'y' if n == 1 else 'ies'}){window_tag}; last voteHash matches leaf")
        if export_voters is not None:
            for r in export_voters:
                if r["tokenName"] == voter:
                    r["txHash"] = history[-1].get("txHash")
                    r["history"] = history


def parse_iso_to_ms(s: str):
    """Parse an ISO-8601 timestamp ending in Z to ms-since-epoch.
    Returns None if parsing fails."""
    try:
        from datetime import datetime, timezone
        # Strip 'Z' and parse as UTC
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return int(datetime.fromisoformat(s).astimezone(timezone.utc).timestamp() * 1000)
    except Exception:
        return None


def ms_to_iso(ms) -> str:
    """Format a ms-since-epoch value as an ISO-8601 UTC string. Returns the
    raw value as-is if it can't be formatted."""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(ms)


def verify_window_for_history(history: list, window_open_ms: int, window_close_ms: int) -> tuple:
    """Confirm every history entry's `timestamp` (ms epoch) falls inside
    [windowOpen, windowClose].

    A recorded timestamp of exactly 0 is treated as *unrecorded* rather than as
    a real 1970-epoch cast time: votes that were replayed while rehydrating a
    Hydra head from its state files (e.g. after a node crash) lose their
    original `Date.now()` stamp and default to 0. Such entries are reported as a
    warning and skipped for the window check, not failed.

    Returns (ok: bool, error_msg: str|None, warn_msg: str|None)."""
    warns = []
    for entry in history:
        v = entry.get("version")
        ts = entry.get("timestamp")
        if ts is None:
            return False, f"history[v{v}] missing timestamp", None
        if not isinstance(ts, (int, float)):
            return False, f"history[v{v}] timestamp not numeric", None
        if ts == 0:
            warns.append(f"history[v{v}] timestamp is 0 (unrecorded — likely a "
                         f"rehydrated/replayed vote); window check skipped for this entry")
            continue
        if ts < window_open_ms:
            return False, (f"history[v{v}] cast before window opened "
                           f"(recorded: {ms_to_iso(ts)} / {ts}ms)"), None
        if ts > window_close_ms:
            return False, (f"history[v{v}] cast after window closed "
                           f"(recorded: {ms_to_iso(ts)} / {ts}ms)"), None
    return True, None, ("; ".join(warns) if warns else None)


def _grid_values(grid: dict) -> list:
    """Enumerate integer grid positions [min, max] at `step`. Mirrors
    hydra/src/routes/settlement.ts:gridValues so zero-fill is identical."""
    if not grid: return []
    step = grid.get("step") or 1
    out = []
    v = grid["min"]
    while v <= grid["max"]:
        out.append(v)
        v += step
    return out


def classify_participation(answers: list) -> str:
    """Classify a voter by what their cast vote actually expressed.

    Returns one of:
      - "active"        at least one answer has a real (non-abstain)
                        selection — the voter expressed a preference on
                        at least one question. From the authority's
                        perspective, this is "participating stake".
      - "abstainOnly"   the signedPayload contains answers but every one
                        is an explicit abstain (`abstain: true` or empty
                        selection). Counts as "showed up but expressed
                        no preference" — typically toward quorum but not
                        toward any tally.
      - "noAnswers"     signedPayload.votes was empty. The middleware
                        normally rejects this, but classify defensively.

    Note: a voter who answered Q1 actively and silently skipped Q2-Q5
    (no answer object for those) is "active" — implicit abstention on
    individual questions doesn't disqualify overall participation.
    """
    if not answers:
        return "noAnswers"
    for ans in answers:
        if ans.get("abstain") is True:
            continue
        sel = ans.get("selection")
        if sel is None or (isinstance(sel, list) and len(sel) == 0):
            continue
        return "active"
    return "abstainOnly"


def _is_abstain(answer: dict) -> bool:
    """An answer is an explicit abstain if `abstain: true` is set; the
    middleware also accepts a missing/empty selection as the same
    intent, so we honour both."""
    if answer.get("abstain") is True:
        return True
    sel = answer.get("selection")
    return sel is None or (isinstance(sel, list) and len(sel) == 0)


def _tally_simple(method: str, selections: list, options: list) -> dict:
    """binary / single-choice / multi-choice — count voters per option
    value, zero-filled across the question's option grid."""
    counts = {int(o["value"]): 0 for o in (options or []) if "value" in o}
    for sel in selections:
        if not isinstance(sel, list):
            continue
        for v in sel:
            iv = int(v)
            counts[iv] = counts.get(iv, 0) + 1
    results = [{"option": o, "count": counts[o]} for o in sorted(counts.keys())]
    return {"method": method, "results": results}


def _tally_range(selections: list, value_range: dict) -> dict:
    """range — single picked value per ballot, returned as a histogram
    over the full valueRange grid (zero-filled)."""
    grid = _grid_values(value_range)
    counts = {v: 0 for v in grid}
    for sel in selections:
        if not isinstance(sel, list) or len(sel) != 1:
            continue
        v = int(sel[0])
        counts[v] = counts.get(v, 0) + 1
    distribution = [{"value": v, "count": counts[v]} for v in sorted(counts.keys())]
    return {"method": "range", "distribution": distribution}


def _tally_ranked(selections: list, options: list) -> dict:
    """ranked — first-preference counts + complete pairwise matrix.

    sortedValues: option `value` ascending (deterministic, independent
    of the ballot-authoring order). matrix[i][j] = ballots ranking
    options[i] above options[j]."""
    sorted_values = sorted(int(o["value"]) for o in (options or []) if "value" in o)
    index_of = {v: i for i, v in enumerate(sorted_values)}
    first_pref = {v: 0 for v in sorted_values}
    n = len(sorted_values)
    matrix = [[0] * n for _ in range(n)]
    for sel in selections:
        if not isinstance(sel, list) or len(sel) == 0:
            continue
        ranking = [int(x) for x in sel]
        first_pref[ranking[0]] = first_pref.get(ranking[0], 0) + 1
        for i in range(len(ranking)):
            ai = index_of.get(ranking[i])
            if ai is None:
                continue
            for j in range(i + 1, len(ranking)):
                aj = index_of.get(ranking[j])
                if aj is None:
                    continue
                matrix[ai][aj] += 1
    return {
        "method": "ranked",
        "firstPreference": [{"option": v, "count": first_pref[v]} for v in sorted_values],
        "pairwise": {"options": sorted_values, "matrix": matrix},
    }


def _tally_weighted(selections: list, options: list) -> dict:
    """weighted — per-option totalPoints (sum of allocations) and
    voterCount (ballots with a non-zero allocation). Voters who omit an
    option contribute zero for that option — mirrors settlement.ts."""
    per_option = {int(o["value"]): [] for o in (options or []) if "value" in o}
    for sel in selections:
        if not isinstance(sel, list):
            continue
        mentioned = set()
        for entry in sel:
            opt = int(entry["option"])
            val = entry["value"]
            per_option.setdefault(opt, []).append(val)
            mentioned.add(opt)
        for opt in list(per_option.keys()):
            if opt not in mentioned:
                per_option[opt].append(0)
    results = []
    for opt in sorted(per_option.keys()):
        vals = per_option[opt]
        results.append({
            "option": opt,
            "totalPoints": sum(vals),
            "voterCount": sum(1 for v in vals if v > 0),
        })
    return {"method": "weighted", "results": results}


def _tally_likert(selections: list, options: list, rating_range: dict) -> dict:
    """likert — per-option rater count and per-rating distribution,
    distribution zero-filled across the full ratingRange grid."""
    per_option = {int(o["value"]): [] for o in (options or []) if "value" in o}
    for sel in selections:
        if not isinstance(sel, list):
            continue
        for entry in sel:
            opt = int(entry["option"])
            val = entry["value"]
            per_option.setdefault(opt, []).append(val)
    grid = _grid_values(rating_range)
    results = []
    for opt in sorted(per_option.keys()):
        ratings = per_option[opt]
        # Distribution keys are stringified to match the published JSON
        # shape (`{"1": 3, "2": 0, ...}`). The middleware's TS source
        # uses Record<number, number>, but JSON numerifies object keys
        # to strings, so the published bytes always have string keys.
        dist = {str(k): 0 for k in grid}
        for r in ratings:
            dist[str(r)] = dist.get(str(r), 0) + 1
        results.append({"option": opt, "count": len(ratings), "distribution": dist})
    return {"method": "likert", "results": results}


def _compute_method_tally(method: str, selections: list, q_def: dict) -> dict:
    """Dispatch to the right per-method tally. Mirrors
    hydra/src/routes/settlement.ts:tallyForMethod 1:1."""
    options = q_def.get("options") or []
    if method in ("binary", "single-choice", "multi-choice", "choice"):
        # `choice` is the backend's name for `single-choice`; treat as alias.
        canonical = "single-choice" if method == "choice" else method
        return _tally_simple(canonical, selections, options)
    if method in ("range", "scale"):
        # `scale` is the backend's authoring name; Hydra publishes as `range`.
        return _tally_range(selections, q_def.get("valueRange"))
    if method == "ranked":
        return _tally_ranked(selections, options)
    if method == "weighted":
        return _tally_weighted(selections, options)
    if method == "likert":
        return _tally_likert(selections, options, q_def.get("ratingRange"))
    if method == "budget":
        # The backend's `budget` (knapsack with per-option costs) maps to
        # Hydra's `weighted` family at tally time — same accumulation
        # over SelectionEntry[] points. Treat as alias.
        return _tally_weighted(selections, options)
    raise NotImplementedError(method)


def retally_question(q_def: dict, voters: list) -> dict:
    """Recompute the canonical `QuestionTally` shape (roleResults +
    abstainedByRole) from per-voter signed answers, for every method
    the system supports."""
    qid = q_def.get("questionId")
    method = q_def.get("method")
    selections_by_role = {}   # {role: [selection lists]}
    abstain_by_role = {}

    for v in voters:
        role = v.get("credentialHrp")
        ans = next((a for a in (v.get("answers") or []) if a.get("questionId") == qid), None)
        if ans is None:
            continue   # voter didn't submit this question — invisible
        if _is_abstain(ans):
            for r in (role, "raw"):
                abstain_by_role[r] = abstain_by_role.get(r, 0) + 1
            continue
        for r in (role, "raw"):
            selections_by_role.setdefault(r, []).append(ans["selection"])

    role_results = {role: _compute_method_tally(method, sels, q_def)
                    for role, sels in selections_by_role.items()}
    return {"method": method, "roleResults": role_results,
            "abstainedByRole": {r: c for r, c in abstain_by_role.items() if c > 0}}


def _diff_method_tally(role: str, method: str, pub: dict, mine: dict) -> list:
    """Compare two MethodTally structures. Returns a list of human-readable
    mismatch strings; empty list = byte-equivalent."""
    diffs = []
    if pub.get("method") and mine.get("method") and pub["method"] != mine["method"]:
        diffs.append(f"role={role}: method mismatch (published={pub['method']} recomputed={mine['method']})")

    if method in ("binary", "single-choice", "multi-choice", "choice"):
        pub_results = {r["option"]: r["count"] for r in (pub.get("results") or [])}
        my_results = {r["option"]: r["count"] for r in (mine.get("results") or [])}
        for opt in sorted(set(pub_results) | set(my_results)):
            p, m = pub_results.get(opt, 0), my_results.get(opt, 0)
            if p != m:
                diffs.append(f"role={role} option={opt}: published count={p} recomputed={m}")
    elif method in ("range", "scale"):
        pub_dist = {r["value"]: r["count"] for r in (pub.get("distribution") or [])}
        my_dist = {r["value"]: r["count"] for r in (mine.get("distribution") or [])}
        for val in sorted(set(pub_dist) | set(my_dist)):
            p, m = pub_dist.get(val, 0), my_dist.get(val, 0)
            if p != m:
                diffs.append(f"role={role} value={val}: published count={p} recomputed={m}")
    elif method == "ranked":
        pub_fp = {r["option"]: r["count"] for r in (pub.get("firstPreference") or [])}
        my_fp = {r["option"]: r["count"] for r in (mine.get("firstPreference") or [])}
        for opt in sorted(set(pub_fp) | set(my_fp)):
            p, m = pub_fp.get(opt, 0), my_fp.get(opt, 0)
            if p != m:
                diffs.append(f"role={role} 1st-pref option={opt}: published={p} recomputed={m}")
        pub_pw = pub.get("pairwise") or {}
        my_pw = mine.get("pairwise") or {}
        if pub_pw.get("options") != my_pw.get("options"):
            diffs.append(f"role={role}: pairwise option order mismatch")
        else:
            opts = pub_pw.get("options") or []
            pm, mm = pub_pw.get("matrix") or [], my_pw.get("matrix") or []
            for i in range(len(opts)):
                for j in range(len(opts)):
                    p = (pm[i][j] if i < len(pm) and j < len(pm[i]) else 0)
                    m = (mm[i][j] if i < len(mm) and j < len(mm[i]) else 0)
                    if p != m:
                        diffs.append(f"role={role} pairwise[{opts[i]}>{opts[j]}]: published={p} recomputed={m}")
    elif method == "weighted" or method == "budget":
        pub_results = {r["option"]: r for r in (pub.get("results") or [])}
        my_results = {r["option"]: r for r in (mine.get("results") or [])}
        for opt in sorted(set(pub_results) | set(my_results)):
            p = pub_results.get(opt, {})
            m = my_results.get(opt, {})
            if p.get("totalPoints", 0) != m.get("totalPoints", 0):
                diffs.append(
                    f"role={role} option={opt} totalPoints: published={p.get('totalPoints',0)} recomputed={m.get('totalPoints',0)}"
                )
            if p.get("voterCount", 0) != m.get("voterCount", 0):
                diffs.append(
                    f"role={role} option={opt} voterCount: published={p.get('voterCount',0)} recomputed={m.get('voterCount',0)}"
                )
    elif method == "likert":
        pub_results = {r["option"]: r for r in (pub.get("results") or [])}
        my_results = {r["option"]: r for r in (mine.get("results") or [])}
        for opt in sorted(set(pub_results) | set(my_results)):
            p = pub_results.get(opt, {})
            m = my_results.get(opt, {})
            if p.get("count", 0) != m.get("count", 0):
                diffs.append(f"role={role} option={opt} count: published={p.get('count',0)} recomputed={m.get('count',0)}")
            pub_dist = p.get("distribution") or {}
            my_dist = m.get("distribution") or {}
            for val in sorted(set(pub_dist) | set(my_dist), key=str):
                pv = int(pub_dist.get(val, 0))
                mv = int(my_dist.get(val, 0))
                if pv != mv:
                    diffs.append(f"role={role} option={opt} likert-value={val}: published={pv} recomputed={mv}")
    return diffs


def compare_published_vs_recomputed(published_qt: dict, recomputed: dict) -> list:
    """Compare a published `QuestionTally` to a recomputed one. Returns
    a list of mismatch strings; empty = byte-equivalent in audit terms."""
    diffs = []
    method = published_qt.get("method") or recomputed.get("method")
    pub_role_results = published_qt.get("roleResults") or {}
    recomp_role_results = recomputed.get("roleResults") or {}
    for role in sorted(set(pub_role_results) | set(recomp_role_results)):
        pub = pub_role_results.get(role) or {}
        mine = recomp_role_results.get(role) or {}
        diffs.extend(_diff_method_tally(role, method, pub, mine))
    pub_abstain = published_qt.get("abstainedByRole") or {}
    recomp_abstain = recomputed.get("abstainedByRole") or {}
    for role in sorted(set(pub_abstain) | set(recomp_abstain)):
        if int(pub_abstain.get(role, 0)) != int(recomp_abstain.get(role, 0)):
            diffs.append(
                f"role={role} abstain: published={pub_abstain.get(role,0)} recomputed={recomp_abstain.get(role,0)}"
            )
    return diffs


def verify_retally_phase(report: Report, results_obj: dict, voters: list, questions: list) -> None:
    """Step 10: independently re-derive per-role / per-option counts
    from each voter's signed answers and confirm they match the published
    `questionTallies` for every Ekklesia method (binary, single-choice,
    multi-choice, range, ranked, weighted, likert, plus the `choice`
    and `scale` and `budget` aliases that some authoring paths use)."""
    report.step("Step 10: re-tally — published per-role counts match independent re-derivation")
    qts = results_obj.get("questionTallies") or []
    if not qts:
        report.fail("results.json has no questionTallies to re-tally")
        return
    if not voters:
        report.fail("no verified voters to re-tally from (audit upstream must have failed)")
        return
    questions_by_id = {q.get("questionId"): q for q in (questions or [])}
    for qt in qts:
        qid = qt.get("questionId") or qt.get("proposalId")
        q_def = questions_by_id.get(qid)
        method = qt.get("method") or (q_def or {}).get("method") \
                 or (next(iter((qt.get("roleResults") or {}).values())) or {}).get("method")
        if not q_def:
            report.fail(f"Q {qid}: question definition missing from ballot — cannot re-tally")
            continue
        # Hydra's tally requires the canonical method name; fall back to
        # the published one if the ballot uses an authoring alias.
        if not q_def.get("method"):
            q_def = {**q_def, "method": method}
        try:
            recomp = retally_question(q_def, voters)
        except NotImplementedError as e:
            report.fail(f"Q {qid} ({method}): re-tally not implemented for method {e!s} — please file an issue")
            continue
        except (KeyError, ValueError, TypeError) as e:
            report.fail(f"Q {qid} ({method}): re-tally aborted on malformed selection: {e}")
            continue
        diffs = compare_published_vs_recomputed(qt, recomp)
        if diffs:
            report.fail(f"Q {qid} ({method}): {len(diffs)} tally mismatch(es)")
            for d in diffs[:8]:
                print(f"           - {d}")
            if len(diffs) > 8:
                print(f"           - ... and {len(diffs)-8} more")
        else:
            report.ok(f"Q {qid} ({method}): published tallies match independently re-derived counts")


def verify_lineage_phase(report: Report, bf: "Blockfrost", instance_utxo: dict,
                         policy_id: str, fingerprint: str, settlement_record: dict = None) -> None:
    """Step 9: walk the (601) UTxO's lineage on Cardano L1 backward through
    any rebalance hops, ending at the original Hydra fanout (input held
    by a script address). At each hop, confirm the inline datum is
    byte-identical to the current (601) datum — datum drift is the only
    way a rebalance can break the audit chain.

    Heuristics for distinguishing fanout vs rebalance:
      - Rebalance: the (601)-bearing input is at a normal user payment
        address (admin wallet).
      - Fanout: the (601)-bearing input is at a script address
        (`addr_test1w...` / `addr1w...`), which is how the Hydra head
        contract holds tokens before fanout.
    """
    report.step("Step 9: (601) UTxO lineage trace — fanout origin & rebalance check")
    full_unit = policy_id + BALLOT_INSTANCE_PREFIX + fingerprint
    expected_datum = instance_utxo.get("inline_datum") or ""
    cur_tx = instance_utxo["tx_hash"]

    rebalance_count = 0
    fanout_seen = False
    drift = False
    HOP_LIMIT = 16
    for hop in range(HOP_LIMIT):
        try:
            tx = bf.tx_utxos(cur_tx)
        except AuditError as e:
            report.fail(f"unable to fetch tx {cur_tx[:16]}...: {e}")
            return
        # Find the input that brings the (601) token in (skip ref/collateral).
        prev = None
        for inp in tx.get("inputs", []):
            if inp.get("collateral") or inp.get("reference"):
                continue
            for amt in inp.get("amount", []):
                if amt.get("unit") == full_unit:
                    prev = inp
                    break
            if prev:
                break
        if prev is None:
            print(f"           [genesis]   tx {cur_tx[:16]}...  no (601) input — original mint")
            break
        is_script_input = prev["address"].startswith(SCRIPT_ADDR_PREFIXES)
        prev_datum = prev.get("inline_datum")
        if is_script_input:
            fanout_seen = True
            print(f"           [fanout]    tx {cur_tx[:16]}...  (601) came from script {prev['address'][:24]}...")
            if settlement_record is not None:
                settlement_record["fanoutTxHash"] = cur_tx
                settlement_record["fanoutScriptAddress"] = prev["address"]
            break
        # Otherwise this is a rebalance hop — datum on the predecessor
        # must match the current (601) datum, else flag drift.
        if prev_datum != expected_datum:
            drift = True
            print(f"           [DRIFT]     tx {cur_tx[:16]}...  predecessor datum DIFFERS from current")
        rebalance_count += 1
        print(f"           [rebalance] tx {cur_tx[:16]}...  predecessor at admin {prev['address'][:24]}...  datum_match={prev_datum == expected_datum}")
        cur_tx = prev["tx_hash"]
    else:
        report.fail(f"lineage walk exceeded {HOP_LIMIT} hops — aborting")
        return

    if drift:
        report.fail("datum drift detected across one or more rebalance hops — current (601) datum does not match a predecessor")
    elif rebalance_count == 0 and fanout_seen:
        report.ok("(601) UTxO traces directly to a Hydra fanout (no rebalances)")
    elif rebalance_count > 0 and fanout_seen:
        report.ok(f"(601) UTxO has {rebalance_count} rebalance hop(s) preserving datum, ultimately from a Hydra fanout")
    elif rebalance_count > 0 and not fanout_seen:
        # Could not unambiguously identify the fanout origin (e.g., the
        # admin re-used a normal payment address for early hops). Datum
        # chain is still consistent — surface as a note rather than fail.
        print(f"           [NOTE] could not unambiguously identify the Hydra fanout in lineage; datum chain is consistent across {rebalance_count} hop(s)")
        report.ok(f"(601) datum preserved across {rebalance_count} lineage hop(s) (fanout origin not deterministically identified)")
    else:
        # No fanout marker AND no rebalance hops AND no inputs carrying
        # (601) — this is the mint/origin tx. Possible only if /finalize
        # has not yet run; we already required (601) to have a results
        # datum in step 1, so this branch is unexpected.
        print("           [NOTE] (601) lineage stopped at a tx with no (601) input and no script origin")


# --- Top-level ballot audit --------------------------------------------------

def audit_one_ballot(report: Report, fingerprint: str, pair: dict, gateway: str,
                     bf: "Blockfrost", opts: dict) -> None:
    report.header(f"Auditing ballot fingerprint {fingerprint}")
    print(f"Policy ID: {pair.get('policyId')}")

    definition_utxo = pair.get("definition")
    instance_utxo = pair.get("instance")

    if not definition_utxo:
        report.fail(f"No (600) definition token UTxO found at admin wallet for {fingerprint}")
        return
    if not instance_utxo:
        report.fail(f"No (601) instance token UTxO found at admin wallet for {fingerprint} (head not yet settled?)")
        return

    # --- Step 1: decode (600) and (601) datums -------------------------------
    report.step("Step 1: decode on-chain inline datums")
    if not definition_utxo.get("inline_datum"):
        report.fail("(600) UTxO has no inline datum")
        return
    if not instance_utxo.get("inline_datum"):
        report.fail("(601) UTxO has no inline datum (ballot not finalized yet?)")
        return

    try:
        ddef = decode_definition_datum(definition_utxo["inline_datum"])
        dins = decode_instance_datum(instance_utxo["inline_datum"])
    except AuditError as e:
        report.fail(str(e))
        return

    print(f"  ballot title:       {ddef['title']}")
    print(f"  namespace:          {ddef['namespace']}")
    print(f"  voting authority:   {ddef['authority']}")
    print(f"  voting window:      {ddef['windowOpen']}  ->  {ddef['windowClose']}")
    print(f"  end epoch:          {ddef['endEpoch']}")
    print(f"  question count:     {ddef['questionCount']}")
    print(f"  ballot CID:         {ddef['ballotCid']}")
    print(f"  ekklesia.merkleRoot: {ddef['merkleRoot']}")
    print(f"  ballot id (601):    {dins['ballotId']}")
    print(f"  results hash (601): {dins['resultsHash']}")
    print(f"  evidence CID (601): {dins['evidenceCid']}")
    print(f"  evidence root (601): {dins['evidenceMerkleRoot']}")
    report.ok("(600) and (601) inline datums decoded successfully")

    # Seed the per-ballot export record with everything we just verified.
    record: dict = opts.setdefault("export_record", {})
    record["fingerprint"] = fingerprint
    record["policyId"] = pair.get("policyId")
    record["ballot"] = {
        "id": dins["ballotId"],
        "title": ddef["title"],
        "namespace": ddef["namespace"],
        "votingAuthority": ddef["authority"],
        "votingWindow": {"open": ddef["windowOpen"], "close": ddef["windowClose"]},
        "endEpoch": ddef["endEpoch"],
        "ballotCid": ddef["ballotCid"],
        "ekklesiaMerkleRoot": ddef["merkleRoot"],
    }
    record["settlement"] = {
        "resultsHash": dins["resultsHash"],
        "evidenceCid": dins["evidenceCid"],
        "evidenceMerkleRoot": dins["evidenceMerkleRoot"],
        "fanoutTxHash": None,
        "fanoutScriptAddress": None,
        "instanceUtxo": {
            "txHash": instance_utxo.get("tx_hash"),
            "outputIndex": instance_utxo.get("output_index", instance_utxo.get("tx_index")),
            "address": instance_utxo.get("address"),
        },
    }

    # --- Step 2: ballot JSON on IPFS reproduces (600) merkle root -----------
    report.step("Step 2: IPFS ballot JSON reconstructs the on-chain (600) merkleRoot")
    ballot_bytes = ipfs_get(gateway, ddef["ballotCid"])
    ballot = json.loads(ballot_bytes)
    questions = ballot.get("questions") or []
    if len(questions) != ddef["questionCount"]:
        report.fail(f"Ballot has {len(questions)} questions but (600) commits to {ddef['questionCount']}")
    leaves = []
    for q in questions:
        # Per ballot.ts: contentHashHex = blake2b_256(JSON.stringify(question))
        # JSON.stringify (no formatting) preserves insertion order; we mirror
        # that with json.dumps(separators=(',',':')) on a dict that was loaded
        # in insertion order (Python 3.7+).
        compact = json.dumps(q, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ch = blake2b_256(compact).hex()
        leaves.append(leaf_hash(q["questionId"], ch))
    rebuilt_root = build_root(leaves).hex()
    if rebuilt_root == ddef["merkleRoot"]:
        report.ok(f"reconstructed merkle root from {len(questions)} questions matches on-chain")
    else:
        report.fail(f"merkle root mismatch: rebuilt={rebuilt_root}  on-chain={ddef['merkleRoot']}")

    # Cache the questions on the export record. Keep all method-relevant
    # metadata (valueRange / ratingRange / voterBudget) so the re-tally
    # phase has the grids it needs to zero-fill identically to the
    # middleware's published results.
    questions_record = []
    for q in questions:
        questions_record.append({
            "questionId": q.get("questionId"),
            "title": q.get("question") or q.get("title"),
            "method": q.get("method") or q.get("voteType"),
            "options": q.get("options") or [],
            "minSelections": q.get("minSelections"),
            "maxSelections": q.get("maxSelections"),
            "requireAnswer": q.get("requireAnswer"),
            "contentHash": q.get("contentHash"),
            "valueRange": q.get("valueRange"),
            "ratingRange": q.get("ratingRange"),
            "voterBudget": q.get("voterBudget"),
        })
    opts.setdefault("export_record", {})["questions"] = questions_record

    # --- Step 3: (601) resultsHash matches IPFS results.json ----------------
    report.step("Step 3: IPFS results.json hashes to the on-chain (601) resultsHash")
    results_bytes = ipfs_get(gateway, f"{dins['evidenceCid']}/results.json")
    h_results = blake2b_256(results_bytes).hex()
    if h_results == dins["resultsHash"]:
        report.ok(f"blake2b_256(results.json) matches resultsHash ({len(results_bytes)} bytes)")
    else:
        report.fail(f"resultsHash mismatch: hashed={h_results}  on-chain={dins['resultsHash']}")
    results = json.loads(results_bytes)

    # --- Step 4: proof-package.json root matches (601) evidenceMerkleRoot --
    report.step("Step 4: IPFS proof-package.json root matches the on-chain evidenceMerkleRoot")
    pkg_bytes = ipfs_get(gateway, f"{dins['evidenceCid']}/proof-package.json")
    pkg = json.loads(pkg_bytes)
    pkg_root = pkg.get("rootHex", "")
    if pkg_root == dins["evidenceMerkleRoot"]:
        report.ok(f"proof package root matches evidenceMerkleRoot")
    else:
        report.fail(f"evidenceMerkleRoot mismatch: package={pkg_root}  on-chain={dins['evidenceMerkleRoot']}")

    voter_files = pkg.get("files") or []
    print(f"         voter count in package: {len(voter_files)}")

    # If --voter was passed, narrow the per-voter checks (steps 5-8) to just
    # that voter. The on-chain commitments (steps 1-4) and lineage (step 9)
    # still run, since the voter wants confirmation that the broader record
    # is genuine before trusting the inclusion proof for their own vote.
    target_voter = None
    if opts.get("voter"):
        try:
            target_voter = resolve_voter_filter(opts["voter"], voter_files)
            print(f"         --voter target: {target_voter} (1 of {len(voter_files)})")
        except AuditError as e:
            report.fail(f"--voter resolution failed: {e}")
            return
        voter_files = [f for f in voter_files if f["name"] == target_voter]

    record["questions"] = []
    record["voters"] = []

    # --- Step 5: per-voter inclusion proofs verify --------------------------
    report.step("Step 5: per-voter merkle inclusion proofs walk back to the on-chain root")
    # Cache per-voter inclusion proofs for downstream use (receipt emission).
    voter_proofs: dict = {}
    for f in voter_files:
        ok = verify_inclusion(f["name"], f["contentHashHex"], f.get("merkleProof") or [], dins["evidenceMerkleRoot"])
        if ok:
            report.ok(f"voter {f['name']} -> root")
            voter_proofs[f["name"]] = {
                "leafHashHex": f.get("leafHashHex"),
                "merkleProof": f.get("merkleProof") or [],
            }
        else:
            report.fail(f"voter {f['name']} -> root  (inclusion proof did not reproduce on-chain root)")

    # --- Step 6: per-voter evidence file hashes match committed voteHashes --
    report.step("Step 6: per-voter evidence file blake2b_256 matches each committed voteHash")
    # Cache the matched evidence per voter for the deeper steps below — keyed
    # by the proof-package's `name` (i.e., the voter token name).
    matched_evidence: dict = {}
    for f in voter_files:
        voter = f["name"]
        expected = f["contentHashHex"]
        # The proof-package commits to whichever vote nonce was the latest at
        # finalize. We probe v1, v2, v3, ... and accept the first that hashes
        # to `expected`. If none match, the audit fails.
        matched_version = None
        matched_obj = None
        last_err = None
        for n in range(1, 11):
            try:
                ev_bytes = ipfs_get(gateway, f"{dins['evidenceCid']}/vote-{voter}-v{n}.json")
            except AuditError as e:
                last_err = e
                break
            ev = json.loads(ev_bytes)
            compact = json.dumps(ev, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if blake2b_256(compact).hex() == expected:
                matched_version = n
                matched_obj = ev
                break
        if matched_version is not None:
            report.ok(f"voter {voter} -> v{matched_version} matches committed voteHash")
            matched_evidence[voter] = {"version": matched_version, "evidence": matched_obj}
            ek = (matched_obj or {}).get("ekklesia") or {}
            voter_record = {
                "voterId": ek.get("voterId"),
                "credentialHrp": ek.get("credentialHrp"),
                "tokenName": voter,
                "voteHash": expected,
                "version": matched_version,
                "calidusId": (ek.get("calidusDeclaration") or {}).get("calidusId"),
                # signedPayload contains the canonical, blake2b-anchored choices.
                "answers": (ek.get("signedPayload") or {}).get("votes") or [],
                # Inclusion proof from step 5, used by --voter-receipt.
                "merkleProof": (voter_proofs.get(voter) or {}).get("merkleProof") or [],
                "leafHashHex": (voter_proofs.get(voter) or {}).get("leafHashHex"),
                # Will be populated by step 7 (sig verify) and step 8 (history).
                "credentialKeyHash": None,
                "txHash": None,
                "history": [],
            }
            record["voters"].append(voter_record)
        else:
            extra = f" (last fetch error: {last_err})" if last_err else ""
            report.fail(f"voter {voter} -> NO version 1..10 of evidence reproduced the voteHash{extra}")

    # --- Step 7: COSE_Sign1 signatures verify -------------------------------
    if opts.get("skip_signatures"):
        report.step("Step 7: per-voter COSE_Sign1 signatures (SKIPPED via --skip-signatures)")
    else:
        verify_signatures_phase(report, voter_files, matched_evidence, dins["ballotId"],
                                export_voters=record["voters"])

    # --- Step 8: vote-history chains intact + voting window enforced --------
    if opts.get("skip_history"):
        report.step("Step 8: per-voter vote-history chain (SKIPPED via --skip-history)")
    else:
        verify_history_phase(report, voter_files, matched_evidence, gateway, dins["evidenceCid"],
                             export_voters=record["voters"],
                             window_open_iso=ddef["windowOpen"],
                             window_close_iso=ddef["windowClose"])

    # --- Step 9: (601) lineage trace ----------------------------------------
    if opts.get("skip_lineage"):
        report.step("Step 9: (601) UTxO lineage trace (SKIPPED via --skip-lineage)")
    else:
        verify_lineage_phase(report, bf, instance_utxo, pair["policyId"], fingerprint,
                             settlement_record=record["settlement"])

    # --- Step 10: re-tally published numbers from voter answers -------------
    # Re-tally needs the FULL voter set; skip in --voter mode (where the
    # caller wants only their inclusion confirmed) or via --skip-retally.
    if target_voter:
        report.step("Step 10: re-tally (SKIPPED — --voter focuses on individual inclusion)")
    elif opts.get("skip_retally"):
        report.step("Step 10: re-tally (SKIPPED via --skip-retally)")
    else:
        verify_retally_phase(report, results, record["voters"], questions)

    # --- Derived participation classification -------------------------------
    # `participation` is a downstream input for the voting authority, not
    # an audit check — there's no published `participation` field on the
    # (601) datum or in results.json to verify against. We just compute
    # it from the voters who already passed every cryptographic check
    # above, so the export carries a clean "active vs abstain-only"
    # signal the authority can join against their voting-power data.
    participation_by_role: dict = {}
    for v in record["voters"]:
        p = classify_participation(v.get("answers") or [])
        v["participation"] = p
        role = v.get("credentialHrp") or "unknown"
        bucket = participation_by_role.setdefault(role, {"active": 0, "abstainOnly": 0, "noAnswers": 0})
        bucket[p] = bucket.get(p, 0) + 1
    record["participation"] = {
        "byRole": participation_by_role,
        "totals": {
            "active":      sum(b["active"]      for b in participation_by_role.values()),
            "abstainOnly": sum(b["abstainOnly"] for b in participation_by_role.values()),
            "noAnswers":   sum(b["noAnswers"]   for b in participation_by_role.values()),
        },
    }

    # --- Tally summary -------------------------------------------------------
    report.step("Tally summary (anchored to verified resultsHash)")
    print(f"  totalVoters:  {results.get('totalVoters')}")
    by_role = results.get("votersByRole") or {}
    for role, n in by_role.items():
        print(f"  {role:14s} voters: {n}")
    p_totals = record["participation"]["totals"]
    print()
    print(f"  participation (derived from signed answers, NOT a published field):")
    print(f"    active        (>=1 non-abstain selection):     {p_totals['active']}")
    print(f"    abstain-only  (every answer is an abstain):    {p_totals['abstainOnly']}")
    if p_totals["noAnswers"]:
        print(f"    no-answers    (empty signedPayload.votes):     {p_totals['noAnswers']}")
    if participation_by_role:
        for role in sorted(participation_by_role.keys()):
            b = participation_by_role[role]
            extra = f", {b['noAnswers']} no-answers" if b["noAnswers"] else ""
            print(f"    by role  {role:8s}: {b['active']} active, {b['abstainOnly']} abstain-only{extra}")
    qts = results.get("questionTallies") or []
    titles = {q["questionId"]: q.get("question", "") for q in questions}
    print(f"  questions:    {len(qts)}")
    for i, qt in enumerate(qts):
        qid = qt.get("questionId") or qt.get("proposalId") or "?"
        title = titles.get(qid, "")
        if len(title) > 60:
            title = title[:57] + "..."
        print(f"    Q{i+1} [{qid}]  {title}")

    # --- Voter-focused vote summary (when --voter is set) -------------------
    if target_voter:
        report.step(f"Your vote — {target_voter}")
        my = next((r for r in record["voters"] if r["tokenName"] == target_voter), None)
        if not my:
            print("  (could not assemble vote summary — see failures above)")
        else:
            print(f"  voterId:        {my['voterId']}")
            print(f"  role:           {my['credentialHrp']}")
            if my.get("calidusId"):
                print(f"  calidus key:    {my['calidusId']}")
            if my.get("credentialKeyHash"):
                print(f"  signing key:    {my['credentialKeyHash']}")
            p = my.get("participation")
            if p == "active":
                print(f"  participation:  active        (you cast at least one non-abstain selection)")
            elif p == "abstainOnly":
                print(f"  participation:  abstain-only  (every answer was an explicit abstain)")
            elif p == "noAnswers":
                print(f"  participation:  no-answers    (signedPayload.votes was empty)")
            print(f"  voteHash leaf:  {my['voteHash']}")
            print(f"  version:        v{my['version']}")
            if my.get("txHash"):
                print(f"  Hydra txHash:   {my['txHash']}")
            print()
            print("  YOUR ANSWERS (cryptographically anchored to the on-chain merkle root):")
            for ans in my["answers"]:
                qid = ans.get("questionId")
                title = titles.get(qid, "")
                if len(title) > 56: title = title[:53] + "..."
                sel = ans.get("selection")
                # Pretty-print selection: list of ints / list of {option, weight}
                if isinstance(sel, list):
                    if sel and isinstance(sel[0], dict):
                        # Likert/scale/budget/weighted entries; field names
                        # vary by method (value/weight/cost/rank). Show all
                        # non-`option` keys so the voter sees their full
                        # canonical answer.
                        parts = []
                        for s in sel:
                            opt = s.get("option")
                            extras = ", ".join(f"{k}={v}" for k, v in s.items() if k != "option")
                            parts.append(f"opt{opt} {{{extras}}}")
                        pretty = "; ".join(parts)
                    else:
                        pretty = ", ".join(str(x) for x in sel)
                else:
                    pretty = str(sel)
                print(f"    Q [{qid}]  {title}")
                print(f"       -> {pretty}")
            if len(my.get("history") or []) > 1:
                print()
                print(f"  RE-VOTE HISTORY ({len(my['history'])} cast votes; latest is what counted):")
                for h in my["history"]:
                    mark = "  COUNTED" if h.get("voteHash") == my["voteHash"] else "superseded"
                    print(f"    v{h['version']}  txHash={h.get('txHash','?')[:16]}...  {mark}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Independent on-chain audit of an Ekklesia ballot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--admin", required=True, help="Voting authority admin wallet address")
    ap.add_argument("--blockfrost-key", required=True, help="Blockfrost project_id (preprod/mainnet)")
    ap.add_argument("--network", default="preprod", choices=sorted(BLOCKFROST_BASE.keys()))
    ap.add_argument("--ipfs-gateway", default=DEFAULT_IPFS_GATEWAY,
                    help=f"IPFS HTTP gateway (default: {DEFAULT_IPFS_GATEWAY})")
    ap.add_argument("--ballot-fingerprint", default=None,
                    help="Audit only the ballot with this 56-hex-char fingerprint")
    ap.add_argument("--voter", default=None,
                    help="Focus per-voter checks on a single voter — accepts a "
                         "bech32 voterId (drep1.../pool1.../stake1.../cc_*1.../calidus1...) "
                         "OR a 58-hex-char on-chain token name. Suppresses per-voter "
                         "noise from other voters; on-chain commitments still verify.")
    ap.add_argument("--export", default=None, metavar="PATH",
                    help="On audit success, write a structured JSON record of the "
                         "verified ballot + per-voter votes (voterId, credential "
                         "key hash, role, answers from signedPayload, txHash, "
                         "history). Feed this into voting-power weighting in a "
                         "separate authority-side tool.")
    ap.add_argument("--voter-receipt", default=None, metavar="PATH",
                    help="With --voter, write a portable receipt JSON containing "
                         "the voter's leaf, full merkle inclusion proof, the "
                         "on-chain root + fanout txHash, and a verification "
                         "recipe. Lets the voter prove inclusion offline forever.")
    ap.add_argument("--skip-signatures", action="store_true",
                    help="Skip step 7 (per-voter COSE_Sign1 signature verification)")
    ap.add_argument("--skip-history", action="store_true",
                    help="Skip step 8 (per-voter vote-history chain + window check)")
    ap.add_argument("--skip-lineage", action="store_true",
                    help="Skip step 9 ((601) UTxO lineage trace)")
    ap.add_argument("--skip-retally", action="store_true",
                    help="Skip step 10 (independent re-tally of published numbers)")
    args = ap.parse_args(argv)
    if args.voter_receipt and not args.voter:
        ap.error("--voter-receipt requires --voter")
    opts = {
        "skip_signatures": args.skip_signatures,
        "skip_history": args.skip_history,
        "skip_lineage": args.skip_lineage,
        "skip_retally": args.skip_retally,
        "voter": args.voter,
    }

    report = Report()
    report.header(f"Ekklesia ballot audit — {args.network}")
    print(f"Admin wallet:    {args.admin}")
    print(f"Blockfrost base: {BLOCKFROST_BASE[args.network]}")
    print(f"IPFS gateway:    {args.ipfs_gateway}")

    bf = Blockfrost(BLOCKFROST_BASE[args.network], args.blockfrost_key)
    try:
        utxos = bf.address_utxos(args.admin)
    except AuditError as e:
        sys.stderr.write(f"\nERROR: {e}\n")
        return 2
    print(f"UTxOs at admin:  {len(utxos)}")

    pairs = find_ballot_pairs(utxos)
    if not pairs:
        report.fail("No ballot tokens found at the admin wallet.")
        return report.summary()
    print(f"Ballot pairs found: {len(pairs)}")
    for fp, p in pairs.items():
        marker = "complete" if (p.get("definition") and p.get("instance")) else "INCOMPLETE"
        print(f"  - {fp} [{marker}]")

    targets = pairs.items()
    if args.ballot_fingerprint:
        if args.ballot_fingerprint not in pairs:
            report.fail(f"Fingerprint {args.ballot_fingerprint} not found at admin wallet.")
            return report.summary()
        targets = [(args.ballot_fingerprint, pairs[args.ballot_fingerprint])]

    exports = []
    for fp, p in targets:
        # Each ballot gets its own export accumulator inside opts. Reset between.
        opts["export_record"] = {}
        try:
            audit_one_ballot(report, fp, p, args.ipfs_gateway, bf, opts)
        except AuditError as e:
            report.fail(f"Audit aborted for {fp}: {e}")
        if opts.get("export_record") and opts["export_record"].get("ballot"):
            exports.append(opts["export_record"])

    rc = report.summary()

    from datetime import datetime, timezone
    audited_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.export:
        if rc != 0:
            sys.stderr.write(
                "\nWARNING: audit failed; export still being written but should not be\n"
                "         used for tabulation. Re-run after the audit passes cleanly.\n"
            )
        envelope = {
            "schemaVersion": "ekklesia.audit/1",
            "auditedAt": audited_at,
            "network": args.network,
            "auditChecks": report.checks,
            "auditFailures": report.failures,
            "auditPassed": rc == 0,
            "voterFilter": args.voter,
            "ballots": exports,
        }
        try:
            with open(args.export, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False, sort_keys=False)
        except OSError as e:
            sys.stderr.write(f"\nERROR writing export to {args.export}: {e}\n")
            return 2
        print(f"\nWrote verified results -> {args.export}")
        print(f"  ballots:        {len(exports)}")
        total_voters = sum(len(b.get('voters') or []) for b in exports)
        print(f"  voter records:  {total_voters}")

    if args.voter_receipt:
        if rc != 0:
            sys.stderr.write(
                "\nERROR: --voter-receipt not written because the audit failed. "
                "Receipts are only valid against a passing audit.\n"
            )
            return rc
        # Find the (single) voter record produced by --voter mode.
        candidates = []
        for b in exports:
            for v in (b.get("voters") or []):
                candidates.append((b, v))
        if len(candidates) != 1:
            sys.stderr.write(
                f"\nERROR: --voter-receipt expected exactly 1 verified voter, found {len(candidates)}.\n"
            )
            return 2
        b, v = candidates[0]
        receipt = {
            "schemaVersion": "ekklesia.voterReceipt/1",
            "auditedAt": audited_at,
            "network": args.network,
            "ballot": {
                "id": b["ballot"]["id"],
                "title": b["ballot"]["title"],
                "namespace": b["ballot"]["namespace"],
                "votingAuthority": b["ballot"]["votingAuthority"],
                "ekklesiaMerkleRoot": b["ballot"]["ekklesiaMerkleRoot"],
                "ballotCid": b["ballot"]["ballotCid"],
            },
            "settlement": {
                "resultsHash": b["settlement"]["resultsHash"],
                "evidenceCid": b["settlement"]["evidenceCid"],
                "evidenceMerkleRoot": b["settlement"]["evidenceMerkleRoot"],
                "fanoutTxHash": b["settlement"].get("fanoutTxHash"),
                "instanceUtxo": b["settlement"]["instanceUtxo"],
            },
            "voter": {
                "voterId": v["voterId"],
                "credentialHrp": v["credentialHrp"],
                "credentialKeyHash": v.get("credentialKeyHash"),
                "calidusId": v.get("calidusId"),
                "tokenName": v["tokenName"],
                "version": v["version"],
                "voteHash": v["voteHash"],
                "leafHashHex": v.get("leafHashHex"),
                "txHash": v.get("txHash"),
                "answers": v["answers"],
                "merkleProof": v["merkleProof"],
            },
            "verificationRecipe": (
                "leaf = blake2b_256(0x00 || hex_decode(voteHash) || utf8(tokenName)). "
                "For each step in merkleProof, compute "
                "running = blake2b_256(0x01 || min_lex(running, sibling) || max_lex(running, sibling)). "
                "Final running value must equal evidenceMerkleRoot, which is committed in the "
                "(601) ballot-instance token's inline datum on Cardano L1. "
                "The (601) UTxO came from the Hydra fanout tx at fanoutTxHash; its inline datum "
                "encodes [ballotId, resultsHash, evidenceCid, evidenceMerkleRoot, schemaVersion] "
                "as a Plutus Constr 0 (CBOR tag 121)."
            ),
        }
        try:
            with open(args.voter_receipt, "w", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2, ensure_ascii=False, sort_keys=False)
        except OSError as e:
            sys.stderr.write(f"\nERROR writing voter receipt to {args.voter_receipt}: {e}\n")
            return 2
        print(f"\nWrote voter receipt -> {args.voter_receipt}")
        print(f"  voterId:       {v['voterId']}")
        print(f"  voteHash:      {v['voteHash']}")
        print(f"  fanoutTxHash:  {b['settlement'].get('fanoutTxHash')}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
