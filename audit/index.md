---
layout: default
title: Auditability
description: How to verify votes and audit ballot results on Ekklesia.
---

Verifiability is a core design principle of Ekklesia. Every ballot produces
cryptographic proofs that allow both individual voters and independent auditors
to verify results.

## Choose Your Guide

<div class="card-grid">

<a href="{{ '/audit/verify-my-vote/' | relative_url }}" class="card">
<h3>Verify My Vote</h3>
<p>I'm a voter and I want to confirm my vote was counted correctly in the final results.</p>
</a>

<a href="{{ '/audit/technical/' | relative_url }}" class="card">
<h3>Technical Auditor Guide</h3>
<p>I need to verify the authenticity and integrity of an entire ballot process from start to finish.</p>
</a>

</div>

## What Proofs Does Ekklesia Provide?

### Merkle Proof of Vote Inclusion

Every finalized ballot produces a **merkle tree** of all votes. The merkle root
is committed on-chain. You can verify that your individual vote is included in
the tree without needing to trust the operator.

### On-Chain Settlement

Final results and the merkle root are recorded on **Cardano L1**. This creates
an immutable, publicly verifiable record that cannot be altered after the fact.

### Voter Signatures

Every vote is signed by the voter's wallet. This means:

- No one can forge a vote on your behalf
- You can prove you cast a specific vote
- The system can detect duplicate or invalid signatures

### Ballot Metadata on IPFS

The ballot structure (options, rules, voter groups) is pinned to **IPFS** and
referenced on-chain. This ensures the ballot rules cannot be changed after
voting begins.
