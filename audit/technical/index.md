---
layout: default
title: Technical Auditor Guide
description:
  Chain-of-custody walkthrough and ready-to-run auditor for verifying an
  Ekklesia ballot from Cardano L1 alone.
---

This guide is for auditors who need to **independently verify** the
cryptographic record produced by Ekklesia using only the public Cardano
ledger and IPFS — no trust in the backend, the Hydra middleware, or any
operator-controlled service.

If those services are offline, archived, or compromised, the audit still
holds: every commitment in the chain is anchored on Cardano L1.

> **Note:** Ekklesia records and tabulates votes. The application of
> voting power, voter eligibility, and thresholds is the responsibility
> of the **voting authority**. This guide covers auditing Ekklesia's
> cryptographic output, not the authority's downstream tabulation.

## What gets verified

A complete audit walks a single chain of cryptographic commitments. Each
hop is an independent hash comparison. A single mismatch anywhere breaks
the chain and signals tampering.

```
Cardano L1
  |
  +-- (600) ballot-definition token UTxO at the admin wallet
  |     inline datum -> ekklesia.merkleRoot, ballotCid, title, window, ...
  |
  |   --[blake2b-256 over question leaves]--
  |
  +-- IPFS-pinned ballot JSON (via ballotCid)
  |     questions[] -> per-question contentHash
  |
  +-- (601) ballot-instance token UTxO at the admin wallet  (after settlement)
  |     inline datum -> resultsHash, evidenceCid, evidenceMerkleRoot, ballotId
  |     L1 lineage    -> walked back through any rebalance hops to the
  |                      original Hydra fanout tx (input at script addr).
  |                      Datum must be byte-identical at every hop.
  |
  |   --[blake2b-256 over results.json bytes]--
  |   --[merkle root over per-voter voteHashes]--
  |
  +-- IPFS-pinned evidence directory (via evidenceCid)
        results.json           -> matches resultsHash
        proof-package.json     -> rootHex matches evidenceMerkleRoot
        vote-{voter}-vN.json   -> blake2b-256 matches each voteHash leaf
          ekklesia.witnesses[] -> ed25519 verifies; CBOR(Sig_structure)
                                  carries the merkleRoot the voter saw;
                                  blake2b-224(pubkey) matches the voter's
                                  declared credential (or calidus key)
        history/{voterId}.json -> chain links: versions strictly ascend,
                                  prevTxHash on entry i = txHash on i-1,
                                  last voteHash matches the committed leaf
```

### The two ballot tokens

Every Ekklesia ballot mints a CIP-68 token pair under a policy controlled
by the voting authority:

- **(600) ballot-definition token** — `asset_name` prefix `00258a50`. Its
  inline datum carries the immutable commitment to the ballot content
  (`ekklesia.merkleRoot`, `ballotCid`, voting window, etc.). This UTxO
  stays on L1 for the lifetime of the ballot.
- **(601) ballot-instance token** — `asset_name` prefix `00259a20`.
  Enters the Hydra head when voting opens, returns to L1 at fanout/settle
  with a final inline datum carrying `resultsHash`, `evidenceCid`, and
  `evidenceMerkleRoot`.

Both tokens share the same 28-byte **ballot fingerprint** suffix
(`blake2b-224` of the ballot namespace), which lets you pair them up.

### What each commitment proves

| Commitment | What it proves |
|---|---|
| `(600).ekklesia.merkleRoot` | The ballot content (questions, options, voting rules) was fixed before voting opened. The pinned ballot JSON cannot have been altered after this point without invalidating the merkle root. |
| `(600).ballotCid` | The pinned ballot JSON is content-addressable on IPFS. Anyone with the CID can fetch the same bytes from any IPFS gateway, forever. |
| `(601).resultsHash` | The published `results.json` is byte-identical to what the Hydra middleware finalized. No post-hoc edits. |
| `(601).evidenceMerkleRoot` | Every individual vote that was counted is committed to L1 via this merkle root. A vote that's not in the tree was not counted. |
| `(601).evidenceCid` | The full evidence directory (per-voter signed payloads, merkle proofs, vote-history chains) is content-addressable on IPFS. |

## Run the auditor

A self-contained Python script is published in [Downloads]({{ '/downloads/' | relative_url }})
that performs every verification step above. It needs PyPI `cbor2`,
`cryptography`, and `bech32`, plus a Cardano data provider key.

```bash
pip install cbor2 cryptography bech32
curl -O https://docs.ekklesia.vote/downloads/_files/audit_ballot.py

python3 audit_ballot.py \
    --admin <voting-authority-address> \
    --blockfrost-key <your-blockfrost-project-id> \
    --network preprod    # or mainnet / preview
```

You provide a Blockfrost project ID for the network the ballot lives on
(`mainnet`, `preprod`, or `preview`). The script does not require any
secret keys, signing material, or Ekklesia API credentials — every check
is read-only against public Cardano L1 and public IPFS.

The script exits `0` if every check passes, `1` if any check fails, and
prints an itemized trace so you can see exactly which step diverged.

To trade depth for speed (e.g., during dev iteration) the deeper steps
can each be skipped independently:

```bash
python3 audit_ballot.py ... --skip-signatures --skip-history --skip-lineage
```

A skipped step is recorded as such; an audit that skipped any step is
not a complete audit.

### What the script verifies

1. The admin wallet holds at least one `(600)`/`(601)` token pair.
2. Both inline datums decode against the documented Plutus shape.
3. The IPFS-pinned ballot JSON re-hashes to `(600).ekklesia.merkleRoot`
   using the lerna-labs/hydra-proof algorithm
   (leaf = `blake2b-256(0x00 || contentHash || name)`,
   parent = `blake2b-256(0x01 || min_lex(L,R) || max_lex(L,R))`,
   pairs duplicated when the leaf count is odd).
4. `blake2b-256(results.json bytes)` matches `(601).resultsHash`.
5. `proof-package.json` rootHex matches `(601).evidenceMerkleRoot`.
6. Every per-voter merkle inclusion proof walks back to the on-chain root.
7. Every per-voter evidence file's `blake2b-256` matches the voteHash leaf
   committed in the proof package. (Re-votes are handled: the script
   probes `vote-{voter}-v1.json`, `v2`, ..., and accepts the version
   that hashes to the committed leaf.)
8. **Per-voter COSE_Sign1 signatures.** For each witness in the matched
   evidence file, the script decodes the COSE_Sign1 envelope, builds the
   canonical `Sig_structure`, and ed25519-verifies it against the public
   key inside the corresponding COSE_Key. It also confirms the COSE
   payload (decoded as ASCII) equals the canonical `signedPayload`'s
   merkleRoot, and that `signedPayload.ballotId` and `nonce` match the
   on-chain ballot id and the matched evidence version respectively.
9. **Per-voter credential match.** `blake2b-224(pubkey)` must match the
   credential carried by the bech32 voterId — the last 28 bytes of the
   bech32-decoded payload for `drep1...`/`stake1...`/`cc_*1...`, or the
   raw 28 bytes for `pool1...`. For pool voters that delegate signing to
   a calidus hot key, the keyhash must match the calidus key declared
   in `ekklesia.calidusDeclaration.calidusId` instead.
10. **Per-voter vote-history chain.** `history/{voterId}.json` is fetched
    from IPFS; versions must ascend strictly from 1 with no gaps, every
    `prevTxHash` must equal the previous entry's `txHash`, and the last
    entry's `voteHash` must equal the committed leaf in the proof package.
11. **Voting-window enforcement.** Every history entry's `timestamp`
    (ms-since-epoch) falls inside `[windowOpen, windowClose]` from the
    (600) datum. A vote outside the window is grounds for hard failure —
    the protocol shouldn't have accepted it.
12. **(601) UTxO lineage.** Starting from the current `(601)` UTxO, the
    script walks back through Cardano L1, looking for any tx that
    consumed a previous `(601)` UTxO. Each rebalance hop's input must
    carry an inline datum byte-identical to the current one. The walk
    ends at the original Hydra fanout transaction — identified by the
    `(601)`-bearing input living at a script address (`addr1w...` /
    `addr_test1w...`), as it would when held by the Hydra head contract
    before fanout.
13. **Independent tally re-derivation.** Per-role / per-option counts
    are recomputed from each voter's signed `signedPayload.votes` and
    compared byte-equal to `results.json:questionTallies`. This catches
    a malicious finalizer that publishes a `results.json` whose hash is
    correct but whose numbers don't match the actual cast votes.
    Coverage is complete across every Ekklesia vote method:
    `binary` / `single-choice` / `multi-choice` (per-option counts),
    `range` / `scale` (zero-filled value-distribution histogram),
    `ranked` (first-preference counts and the full pairwise preference
    matrix used by Borda / Condorcet / Schulze / IRV / etc.),
    `weighted` / `budget` (per-option `totalPoints` sums and
    `voterCount`s), and `likert` (per-option rater counts plus
    distribution zero-filled across the rating grid). The authoring
    aliases `choice`, `scale`, and `budget` resolve to their canonical
    Hydra method at compare time.

### For voting authorities — exporting verified results

Ekklesia produces an immutable cryptographic record. The voting
authority is responsible for everything downstream — applying voting
power, checking eligibility, computing weighted tallies, and publishing
final outcomes. The auditor exposes that hand-off cleanly:

```bash
python3 audit_ballot.py \
    --admin <authority-address> \
    --blockfrost-key <project-id> \
    --network mainnet \
    --export results.verified.json
```

The exported JSON only ships data that *passed* the audit. Its envelope
records exactly which checks passed (so the export is itself
self-describing about what's been verified) and the per-ballot record
includes everything needed for weighting:

```json
{
  "schemaVersion": "ekklesia.audit/1",
  "auditedAt": "2026-...",
  "network": "mainnet",
  "auditChecks": 33,
  "auditFailures": 0,
  "auditPassed": true,
  "ballots": [
    {
      "fingerprint": "...",
      "policyId": "...",
      "ballot": { "id", "title", "votingAuthority", "votingWindow",
                  "endEpoch", "ballotCid", "ekklesiaMerkleRoot" },
      "settlement": { "resultsHash", "evidenceCid",
                      "evidenceMerkleRoot", "fanoutTxHash",
                      "instanceUtxo" },
      "questions": [ { "questionId", "title", "method", "options",
                       "minSelections", "maxSelections" } ],
      "voters": [
        {
          "voterId":           "drep1y2vpdk6...",
          "credentialHrp":     "drep",
          "credentialKeyHash": "9816db59cc3cefc2...",
          "tokenName":         "22227b00...",
          "calidusId":         null,
          "version":           1,
          "voteHash":          "1a9a0a88...",
          "txHash":            "2429ab86...",
          "answers":           [ { "questionId", "selection" } ],
          "history":           [ ... ]
        }
      ]
    }
  ]
}
```

Each voter's `credentialKeyHash` is the canonical 28-byte Cardano key
hash you'd use to look up that voter's voting power on-chain — the DRep
delegation register for `drep` voters, the SPO pledge UTxOs for `pool`,
the stake delegation snapshot for `stake`, and so on. `answers` carries
the exact, byte-stable choices the voter signed, so weighting is just a
matter of joining your eligibility/power data against `voterId` and
applying it to `answers`.

`fanoutTxHash` and `instanceUtxo` give you a permanent on-chain anchor
to cite when publishing final results.

#### Participation classification

Each voter record carries a derived `participation` field, and a
ballot-level `participation` block aggregates by role:

- `"active"` — at least one of the voter's signed answers carries a
  real (non-abstain) selection. This is what most authorities want to
  count as "participating stake" — the voter actually expressed a
  preference somewhere in the ballot.
- `"abstainOnly"` — the voter's `signedPayload` contains answers but
  every single one is an explicit abstain (`abstain: true` or empty
  selection). They showed up but expressed no preference on anything.
  Authorities typically count this toward quorum but not toward any
  per-question tally.
- `"noAnswers"` — `signedPayload.votes` was empty. The middleware
  normally rejects this; surfaced defensively in case a future protocol
  variant accepts it.

A voter who answers Q1 actively and silently skips Q2-Q5 (no answer
object emitted for those questions) is `"active"`. Implicit abstention
on individual questions does not disqualify overall participation —
those questions just don't contribute to that voter's per-question
tally bucket.

This field is **derived**, not anchored on-chain. There is no
`participation` value in the `(601)` datum or `results.json` for the
audit to verify against. The classification is computed from each
voter's `answers`, all of which *are* cryptographically anchored, so
the result inherits the same trust as the underlying signed payload.

```json
"participation": {
  "byRole": {
    "drep": { "active": 4, "abstainOnly": 0, "noAnswers": 0 },
    "pool": { "active": 3, "abstainOnly": 0, "noAnswers": 0 }
  },
  "totals": { "active": 7, "abstainOnly": 0, "noAnswers": 0 }
}
```

### Rebalances are non-fatal

Step 11 explicitly tolerates rebalance hops, so the voting authority can
respin the `(600)` and `(601)` UTxOs to adjust their lovelace amounts —
for example when a Cardano protocol-parameter update raises minUTxO.
What it does *not* tolerate is **datum drift**: if any rebalance hop's
inline datum differs from the current one, the audit fails.

### What the script does not verify (planned future work)

A handful of forensic checks remain outside the script's current scope.
None of them gate the integrity of the cryptographic record — the
existing 13 checks already anchor every byte of every vote to Cardano
L1 — but each one closes a narrower attack surface and is worth running
when a ballot's stakes warrant it. These are slated for a future
release; the recipes below let an auditor do them by hand today.

- **IPFS content-address verification.** The script trusts whichever
  gateway it talks to. Mitigation: pass `--ipfs-gateway` pointing at a
  gateway you control (or your local Kubo node), and/or fetch the same
  CID from multiple independent gateways and confirm byte-identical
  responses. A future `--ipfs-gateway A,B,C` mode will fold this into
  the script.
- **Original prepare/mint transaction.** Step 12 traces the (601) back
  to a Hydra fanout but does not trace the (600) back to its mint, nor
  does it re-derive the timelocked native-script policy that minted
  both tokens. By hand: query the (600) UTxO's tx history to find its
  mint transaction, fetch the policy script, confirm it's a `timelock`
  with the authority key as the sole signer and a sensible
  `invalidHereafter` slot.
- **Calidus → pool delegation on L1.** For pool voters using a calidus
  hot key, the script confirms the COSE signature was made by the
  declared calidus key but does not look up the calidus registration
  certificate on-chain to confirm that calidus key is currently
  delegated to the declared pool. By hand: query the pool's calidus
  registration via Koios `/pool_calidus_keys` (or equivalent) and
  compare to `ekklesia.calidusDeclaration.calidusId` for each pool
  voter.

Independently of those, two checks fall *outside* the audit by design,
because they're the voting authority's policy decisions rather than
cryptographic facts:

- **Voter eligibility.** Whether a given voter was authorised to vote
  (e.g., DRep registered at the snapshot epoch, SPO with non-zero
  pledge, address holding the required token at the snapshot height) is
  the authority's call, not the auditor's. The script's `--export`
  output gives the authority the canonical `voterId`/`credentialKeyHash`
  list to reconcile against their eligibility set.
- **Voting power, exclusion, and "winning" thresholds.** Applying
  weight per voter, dropping voters who fail eligibility, and deciding
  whether a tally crosses participation or majority thresholds are
  authority concerns. The audit guarantees the *raw* counts; a separate
  authority-side tool (planned) will consume the `--export` JSON and
  publish weighted, threshold-adjusted final results.

## Verify by hand

If you don't trust the script, every step is reproducible from
first-principles tooling. Below is the manual recipe.

### Phase 1 — find the ballot tokens

Query the admin wallet's UTxOs from any Cardano data provider:

```bash
curl -H "project_id: $BLOCKFROST_KEY" \
  "https://cardano-preprod.blockfrost.io/api/v0/addresses/$ADMIN/utxos?count=100"
```

In the response, look for native assets whose 56-character `asset_name`
starts with:

- `00258a50` — `(600)` ballot-definition token
- `00259a20` — `(601)` ballot-instance token

The 56 hex characters after the prefix are the **ballot fingerprint**.
Both tokens of a ballot share the same fingerprint.

### Phase 2 — decode the inline datums

The Plutus inline datum on each UTxO is a CBOR `Constr 0` with the shape:

```
(600) — Constr 0 [ [ title:Bytes,
                     namespace:Bytes,
                     authority:Bytes,
                     merkleRoot:Bytes,
                     ballotCid:Bytes,
                     questionCount:Int,
                     windowOpen:Bytes,
                     windowClose:Bytes,
                     endEpoch:Int ],
                   schemaVersion:Int ]

(601) — Constr 0 [ [ ballotId:Bytes,
                     resultsHash:Bytes,
                     evidenceCid:Bytes,
                     evidenceMerkleRoot:Bytes ],
                   schemaVersion:Int ]
```

Any standard CBOR library (Python `cbor2`, JS `cbor-x`, Rust `ciborium`)
parses this shape directly. Plutus `Constr 0` corresponds to **CBOR tag
121** with the inner list as its value.

### Phase 3 — reconstruct the ballot merkle root

Fetch the ballot JSON from any IPFS gateway:

```bash
curl https://ipfs.io/ipfs/$BALLOT_CID -o ballot.json
```

For each entry in `ballot.json:questions[]`:

1. Compute `contentHashHex = blake2b-256(JSON.stringify(question))`
   — JS-default serialization, no whitespace, insertion-order keys.
2. Compute `leaf = blake2b-256(0x00 || hex_decode(contentHashHex) || utf8(questionId))`.

> **Note:** This hash uses **insertion-order** keys at every `specVersion`,
> including `ekklesia/2.0`. The canonical sorted-key JSON that 2.0
> introduced applies to the per-voter evidence envelopes in Phase 6, not
> here. Question objects are not alphabetical, so sorting their keys
> rebuilds a root that will not match `(600).ekklesia.merkleRoot`.

Build the merkle tree by pairing leaves left-to-right; if the count is
odd, the last leaf is paired with itself. Each parent is
`blake2b-256(0x01 || min_lex(L, R) || max_lex(L, R))` where ordering is
by lowercase hex string.

The root must equal the on-chain `(600).ekklesia.merkleRoot`.

### Phase 4 — verify settlement artifacts

Fetch `results.json` and `proof-package.json` from the evidence
directory:

```bash
curl https://ipfs.io/ipfs/$EVIDENCE_CID/results.json -o results.json
curl https://ipfs.io/ipfs/$EVIDENCE_CID/proof-package.json -o proof-package.json
```

- `blake2b-256(results.json bytes)` must equal `(601).resultsHash`.
- `proof-package.json:rootHex` must equal `(601).evidenceMerkleRoot`.

### Phase 5 — verify per-voter inclusion

For every entry in `proof-package.json:files[]`:

1. Compute the leaf as in Phase 3 using `name` and `contentHashHex`.
2. Walk the inclusion proof: start with the leaf, and for each step
   replace the running hash with `parentHash(running, sibling)` (using
   the same lex-sort rule).
3. The final hash must equal the on-chain `evidenceMerkleRoot`.

### Phase 6 — verify each voter's evidence

For each voter, fetch the evidence file:

```bash
curl https://ipfs.io/ipfs/$EVIDENCE_CID/vote-$VOTER-v1.json
```

Re-hash the envelope and compare the result to that voter's
`contentHashHex` in the proof package. **The serialization depends on the
ballot's `specVersion`**, which you read from the already-verified
`results.json`:

```
ekklesia/2.0 and later : blake2b-256(canonical_json(evidence))
earlier                : blake2b-256(JSON.stringify(evidence))
```

Canonical JSON here means compact (no whitespace), UTF-8, with object keys
sorted lexicographically at every level of nesting. `JSON.stringify` is
also compact and UTF-8, but keeps keys in insertion order.

Two properties of the envelope keep this simple enough to implement in any
language, and both are guarantees of the format rather than accidents of a
particular ballot:

- **Every numeric value is an integer.** `selection` values are option
  indices or integer ratings. Envelopes never carry fractional numbers, and
  never carry integers outside the range that survives an IEEE-754 double
  (±2^53 − 1). This is what lets a canonicalizer skip the number-formatting
  rules that make [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) fiddly.
- **Every object key is an ASCII protocol field name.** Keys come from the
  format (`specVersion`, `surveyTxId`, `responderRole`, `answers`,
  `ekklesia`, `questionId`, `selection`, and the `ekklesia` sub-keys), never
  from ballot content. Sorting them by code point and sorting them by UTF-16
  code unit therefore give the same order.

String **values** may be any UTF-8. Serialize them raw, escaping only `"`,
`\`, and C0 control characters. Candidate labels never appear in an
envelope at all, so no restriction on ballot text follows from any of this.

This distinction is load-bearing. The envelope's top-level keys are
`specVersion, surveyTxId, responderRole, answers, ekklesia`, which is not
alphabetical, so the two encodings produce different bytes and different
hashes. Using the wrong one makes **every** voter fail this phase at once.

A total failure here is the signature of an encoding mismatch rather than
tampering. Each envelope is committed separately, so real tampering shows
up on individual voters, not all of them simultaneously.

> **Note:** This canonical form applies to the evidence envelope only. It
> does **not** apply to the question `contentHash` in Phase 3, which stays
> in insertion order at every `specVersion`.

If the voter re-voted, try `v2`, `v3`, etc. Whichever version hashes to
the committed value is the one that was counted. The earlier versions
exist on IPFS for chain-of-custody but did not make it into the final
tally.

### Phase 7 — verify each voter's signature

For each entry in `ekklesia.witnesses[]` of the matched evidence file:

1. CBOR-decode `coseSign1Hex` into the 4-element array
   `[protected_bstr, unprotected, payload, signature]`.
2. CBOR-decode `coseKeyHex` and read the 32-byte ed25519 public key from
   map label `-2` (`kty=1` OKP, `alg=-8` EdDSA, `crv=6` Ed25519).
3. Build `Sig_structure = ["Signature1", protected_bstr, h'', payload]`
   and CBOR-encode it.
4. ed25519-verify the encoded `Sig_structure` against `signature` with
   the public key from step 2.
5. The COSE payload, decoded as ASCII, must equal the merkleRoot
   recomputed as `blake2b-256(JSON.stringify(signedPayload))`. This
   confirms the bytes the voter actually signed match the canonical
   votes listed in `signedPayload.votes`.
6. `blake2b-224(pubkey)` must match the voter's credential — the last
   28 bytes of the bech32-decoded `voterId` (or, for pool voters with a
   calidus declaration, the calidus key hash from
   `ekklesia.calidusDeclaration.calidusId`).

### Phase 8 — verify the vote-history chain

Fetch the history file:

```bash
curl https://ipfs.io/ipfs/$EVIDENCE_CID/history/$VOTER_ID.json
```

This is an array of one entry per cast vote (registration + each
update). Confirm:

- `version` ascends strictly from 1 with no gaps.
- `prevTxHash` on entry i equals `txHash` on entry i-1 (and is absent on
  the first entry).
- The last entry's `voteHash` equals the committed leaf in the proof
  package.
- Optionally, each entry's `voteHash` equals the blake2b-256 of the
  evidence file at `vote-{voterId-tokenname}-v{version}.json`.

### Phase 9 — verify the (601) lineage on L1

Starting from the current `(601)` UTxO's `tx_hash`, fetch that
transaction's inputs and outputs:

```bash
curl -H "project_id: $BLOCKFROST_KEY" \
  "https://cardano-preprod.blockfrost.io/api/v0/txs/$TX_HASH/utxos"
```

If any input carries the `(601)` token:

- The input's `inline_datum` must be byte-identical to the current
  `(601)` UTxO's datum (no drift).
- If the input lives at a normal payment address (the admin wallet),
  this is a **rebalance** — recurse into that input's tx.
- If the input lives at a script address (`addr_test1w...` /
  `addr1w...`), this is the original **Hydra fanout** — the chain
  terminates here.

A clean lineage looks like: current → 0..N rebalances (datum preserved)
→ Hydra fanout (script-address input) → done.

## What this audit can and cannot tell you

**Can** — that the published results, the published evidence, and the
on-chain commitments form a single internally-consistent cryptographic
record. No one (including the voting authority) can change any of these
after the fact without invalidating the chain.

**Cannot** — that the voters were entitled to vote the way they did. The
voting authority's eligibility, voting-power, and threshold rules apply
to the cryptographic record produced by Ekklesia. Final published results
may differ from this raw tally once the authority applies its weighting
and qualification criteria.

## References

- Algorithm reference (TypeScript):
  [`@lerna-labs/hydra-proof`](https://www.npmjs.com/package/@lerna-labs/hydra-proof)
- Canonicalization rules:
  `helper/canonicalJson.js` in the Ekklesia backend
- Hash function: `blake2b` with 32-byte digest, no key, no salt, no
  personalization. Output as lowercase hex.
