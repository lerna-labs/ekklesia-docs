---
layout: default
title: Hydra & Architecture
description: How Ekklesia uses Hydra L2 state channels for verifiable voting.
---

## Why Hydra?

Cardano's Hydra protocol provides **L2 state channels** — isolated, high-speed
transaction environments that settle back to the L1 mainchain. Ekklesia uses
Hydra to process votes as real transactions, providing:

- **Speed** — Votes are processed inside the Hydra head without waiting for L1
  block confirmations
- **Low cost** — No per-vote L1 transaction fees during the voting period
- **Verifiability** — All votes are real transactions with cryptographic
  signatures
- **On-chain settlement** — Final results are committed to Cardano L1

## Ballot Lifecycle on Hydra

### 1. Prepare (L1)

Two CIP-68 style tokens are minted on Cardano L1:

- **(600) Reference token** — The ballot definition, pinned to IPFS and anchored
  on L1 as an immutable record of the ballot structure
- **(601) Instance token** — Committed into the Hydra head and used to transit
  the state channel containing results

### 2. Start

A Hydra head is opened by committing the (601) ballot instance token along with
gas UTxOs. The ballot definition is loaded from IPFS and cached for vote
validation.

### 3. Vote

Voters submit votes as transactions inside the Hydra head. Each vote is
validated against the ballot's rules (vote type, selection constraints, etc.).

The **voting administrator records all transactions** within the head. However,
each transaction is **cryptographically signed by the voter** — the
administrator cannot forge, alter, or fabricate votes. The ledger rules provide
a replayable history of all voting activity.

### 4. Finalize

While the head is still open, a merkle tree of all votes is constructed. The
merkle root and result data are written to the ballot results token inside the
head. This must happen before closing, as closing the head prevents all further
updates.

### 5. Close

The Hydra head is closed. No further votes or updates can be submitted.

### 6. Settle (L1)

The (601) instance token's inline datum — now containing the final results and
merkle root — is settled back to Cardano L1, creating a permanent,
tamper-evident record that can be independently audited.

## Voting Power Is Not Our Concern

Ekklesia treats **every voter as one voter casting one vote**. The system does
not apply voting power, stake weighting, or eligibility thresholds.

This is a deliberate design decision. The cryptographic proof of _how_ a user
voted is separate from the question of _how much weight_ that vote carries.
Voting power snapshots, voter eligibility criteria, and threshold calculations
are likely to be contested — these concerns should be resolved independently
from the voting infrastructure itself.

Ekklesia's job is to **report the facts firmly within its control**: who voted,
what they voted for, and the cryptographic proof that each vote is authentic.
Power weighting and eligibility are applied at the tabulation layer, not at the
voting layer.

## Security Model

Ekklesia's security guarantees come from:

- **Cardano L1** — Settlement layer provides finality and tamper-evidence
- **Hydra ledger rules** — Provide a replayable history of all voting activity
  that should match the audit results
- **Cryptographic signatures** — Every vote is signed by the voter's wallet
  keys; the administrator cannot forge votes
- **Merkle proofs** — Allow individual vote verification against the on-chain
  root
- **IPFS** — Ballot metadata is content-addressed and immutable; ballot rules
  cannot be changed after minting

## Why Not "Off-Chain Voting"?

Traditional off-chain voting systems ask you to trust the operator's database.
Ekklesia is different:

- Votes are **signed transactions**, not database entries
- The voting environment produces a **replayable ledger** of all activity
- Results are **settled on-chain**, not just published
- Anyone can **independently verify** results using merkle proofs

The Hydra head provides a trust-minimized execution environment — votes happen
off the main chain for speed, but the ledger history and on-chain settlement
mean results are independently verifiable.
