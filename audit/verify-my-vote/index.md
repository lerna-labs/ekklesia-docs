---
layout: default
title: Verify My Vote
description: How to confirm your vote was included in the final ballot results.
---

After a ballot closes and results are finalized, you can independently
verify that your vote was counted correctly — without trusting Ekklesia,
the voting authority, or any operator-controlled service.

## What you'll need

- Your **voter identifier** (e.g., `stake1...`, `drep1...`, `pool1...`,
  or a CIP-95 credential hex). This is what was hashed to produce the
  voter token your wallet held during the vote.
- The **voting authority's admin wallet address** for the ballot.
- A **Blockfrost project ID** for the network the ballot lives on
  (mainnet, preprod, or preview). Free tier is sufficient.

## How verification works

When a ballot is finalized, Ekklesia publishes a **merkle tree** whose
leaves are every counted vote. The merkle root is committed to Cardano
L1 in the `(601)` ballot-instance token's inline datum.

To verify your vote, the auditor:

1. Reads the merkle root straight from L1.
2. Fetches the published proof package from IPFS (its CID is also on L1).
3. Reproduces the merkle path for *your* voter ID from the leaf back to
   the root.

If the path reproduces the on-chain root, your exact vote — choices,
signature, and all — is provably part of the dataset that produced the
on-chain result.

<div class="callout callout-info">
<strong>What this proves:</strong> Your vote is in the merkle tree, in
the form you signed it, and it has not been altered, omitted, or
fabricated since the ballot closed.
</div>

## Step-by-step verification

The same audit tool used by technical auditors has a `--voter` mode that
runs every relevant check for a single voter and prints a focused
summary of the cast vote. Download `audit_ballot.py` from
[Downloads]({{ '/downloads/' | relative_url }}) and run:

```bash
pip install cbor2 cryptography bech32

python3 audit_ballot.py \
    --admin <voting-authority-address> \
    --blockfrost-key <your-blockfrost-project-id> \
    --network mainnet \
    --voter <your-voter-id>
```

`--network` accepts `mainnet`, `preprod`, or `preview`. `--voter` accepts
either:

- a bech32 voter identifier — `drep1...`, `pool1...`, `stake1...`,
  `stake_test1...`, `cc_cold1...`, `cc_hot1...`; or
- the 58-character hex token name that appears on-chain (the script
  prints the full list when you run a full audit).

The on-chain commitments (steps 1–4) and the (601) UTxO lineage trace
(step 9) still run, so you confirm the *whole record* is genuine before
trusting the inclusion proof for your individual vote. The per-voter
checks (steps 5–8) run only for your voterId.

### What the focused output tells you

```
--- Step 5: per-voter merkle inclusion proofs walk back to the on-chain root
  [OK]   voter <yours> -> root
--- Step 6: per-voter evidence file blake2b_256 matches each committed voteHash
  [OK]   voter <yours> -> v1 matches committed voteHash
--- Step 7: per-voter COSE_Sign1 signatures verify
  [OK]   voter <yours>: ed25519+message+credential verified — matched drep key credential
--- Step 8: per-voter vote-history chain integrity
  [OK]   voter <yours>: history chain intact (1 entry); last voteHash matches leaf
--- Your vote — <token name>
  voterId:        <bech32 you provided>
  signing key:    <blake2b-224 of your wallet's signing pubkey>
  voteHash leaf:  <leaf in the on-chain merkle tree>
  version:        v1
  Hydra txHash:   <the L2 transaction that recorded the vote>

  YOUR ANSWERS (cryptographically anchored to the on-chain merkle root):
    Q [...]  <question title>
       -> 1
    Q [...]  <question title>
       -> opt1 {value=1}; opt2 {value=5}; ...
```

Five `[OK]` lines and the closing **AUDIT PASSED** banner mean your vote
is provably in the final on-chain merkle tree, was signed by your
wallet, and the displayed answers are byte-identical to what you signed
when you cast the vote. If you re-voted, the script also prints a
**RE-VOTE HISTORY** block listing every cast version with the latest
flagged `COUNTED` and the rest `superseded`.

If anything fails, the script tells you exactly which step diverged and
on what hash, so you can take it up with the voting authority with
specific evidence in hand.

## Save a portable receipt

Pass `--voter-receipt receipt.json` along with `--voter` to write a
small JSON file that captures everything needed to re-prove your
inclusion later, offline, against any future Cardano indexer:

```bash
python3 audit_ballot.py \
    --admin <voting-authority-address> \
    --blockfrost-key <your-blockfrost-project-id> \
    --network mainnet \
    --voter <your-voter-id> \
    --voter-receipt my-vote-receipt.json
```

The receipt contains:

- The on-chain anchors — `evidenceMerkleRoot`, `resultsHash`,
  `fanoutTxHash`, the (601) UTxO reference — so anyone reading the
  receipt years from now knows exactly where on Cardano L1 to look.
- Your `voteHash`, `tokenName`, and full merkle inclusion proof
  (sibling hashes from your leaf to the on-chain root).
- Your `signedPayload.votes` — the byte-stable answers you signed.
- A short `verificationRecipe` text describing the algorithm step by
  step, so a third party can verify the proof from first-principles
  without running this script at all.

If something happens to ekklesia.vote, the IPFS pin, or anything else
later, the receipt plus a Cardano explorer is enough to prove your
vote was counted.

For a deeper walk-through of every commitment hop, what each one proves,
and how to verify by hand from first-principles tooling, see the
[Technical Auditor Guide]({{ '/audit/technical/' | relative_url }}).

## Why final results may differ from preliminary

During a live ballot, provisional results may be displayed periodically
as a convenience. These are **strictly informational**.

Ekklesia tabulates the cryptographic record of who voted and how. The
application of **voting power, voter eligibility, and thresholds** is
the responsibility of the **voting authority** — the organization
conducting the vote. These factors are applied to the auditable results
produced by Ekklesia, not by Ekklesia itself.

Final published results may differ from provisional displays once the
voting authority applies their eligibility and weighting criteria.
