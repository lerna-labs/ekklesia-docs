---
layout: default
title: Technical Auditor Guide
description:
  Complete guide for auditing the integrity of an Ekklesia ballot from end to
  end.
---

This guide is for auditors who need to independently verify the cryptographic
record produced by Ekklesia — from ballot creation through vote collection to
on-chain settlement.

> **Note:** Ekklesia records and tabulates votes. The application of voting
> power, voter eligibility, and thresholds is the responsibility of the voting
> authority. This guide covers auditing Ekklesia's cryptographic output, not the
> voting authority's tabulation.

## Audit Scope

A complete audit of Ekklesia's output verifies:

1. **Ballot integrity** — The ballot structure on-chain matches what was
   presented to voters
2. **Vote authenticity** — Every recorded vote has a valid cryptographic
   signature from its claimed signer
3. **Vote inclusion** — The merkle tree correctly represents all recorded votes
4. **Ledger consistency** — The replayable transaction history inside the Hydra
   head is complete and consistent
5. **On-chain settlement** — The L1 settlement transaction contains the correct
   merkle root and result data from the (601) token's inline datum

## Prerequisites

- Familiarity with Cardano transaction structure and metadata
- Ability to query Cardano L1 (via Blockfrost, Koios, or a local node)
- Understanding of merkle trees and inclusion proofs
- Access to IPFS (for ballot metadata retrieval)

## Audit Process

_Detailed audit procedures coming soon. This section will cover:_

### Phase 1: Ballot Verification

- Retrieve the ballot minting transaction from L1 (CIP-68 token pair)
- Fetch ballot metadata from IPFS using the (600) reference token
- Verify the ballot structure (questions, vote types, options) matches what was
  presented to voters

### Phase 2: Vote Verification

- Obtain the complete set of vote transactions from the Hydra ledger history
- Verify each vote's cryptographic signature against the claimed signer
- Confirm that the ledger history is consistent and complete (no gaps, no
  unsigned transactions)

### Phase 3: Merkle Tree Verification

- Reconstruct the merkle tree from the verified vote set
- Confirm the computed merkle root matches the root in the (601) token's inline
  datum
- Verify individual vote inclusion proofs against the root

### Phase 4: Settlement Verification

- Verify the settlement transaction on L1
- Confirm the (601) token's inline datum contains the expected merkle root and
  result data
- Verify the datum matches the reconstructed results from Phase 3

## Tools

_Auditing tools and scripts will be published here as they become available._
