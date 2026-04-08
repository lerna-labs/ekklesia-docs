---
layout: default
title: Ekklesia
description: Verifiable on-chain voting on Cardano — powered by Hydra.
---

## What is Ekklesia?

Ekklesia is a voting platform for **verifiable and transparent on-chain voting
on Cardano**. It supports votes for all kinds of voter groups — DReps, SPOs,
token or NFT holders, or anyone with a Cardano wallet. Ekklesia also supports
MultiSigs and CLI-based authentication via CardanoSigner.

Ekklesia is developed by [Adam Dean](https://x.com/adamkdean) &
[Mad Orkestra](https://bsky.app/profile/madorkestra.com), with funding from
[IOG](https://iog.io), [Intersect](https://intersectmbo.org) and
[Project Catalyst Fund 14](https://projectcatalyst.io/).

## Why "Hydra-Powered" Voting?

Unlike off-chain voting systems where you trust the operator, Ekklesia leverages
**Cardano's Hydra L2 state channels** to process votes. This means:

- **Every vote is a real transaction** processed inside a Hydra head
- **Final results are settled on-chain** (Cardano L1), creating a permanent,
  tamper-evident record
- **Merkle proofs** allow anyone to independently verify that their vote was
  included in the final tally
- **The security model inherits from Cardano** itself, not from a centralized
  server

This is not "off-chain voting with a blockchain receipt." The entire voting
process runs through cryptographic state channels with on-chain settlement.

## Documentation Sections

<div class="card-grid">

<a href="{{ '/getting-started/' | relative_url }}" class="card">
<h3>Getting Started</h3>
<p>How to connect your wallet and cast your first vote on Ekklesia.</p>
</a>

<a href="{{ '/vote-types/' | relative_url }}" class="card">
<h3>Vote Types</h3>
<p>Default, Budget, Scale, Ranked — the different voting mechanisms and their rules.</p>
</a>

<a href="{{ '/api/' | relative_url }}" class="card">
<h3>API Reference</h3>
<p>Integrate with Ekklesia — query ballots, fetch results, and submit votes programmatically.</p>
</a>

<a href="{{ '/hydra/' | relative_url }}" class="card">
<h3>Hydra & Architecture</h3>
<p>How Hydra state channels power the voting process and what that means for security.</p>
</a>

<a href="{{ '/audit/' | relative_url }}" class="card">
<h3>Auditability</h3>
<p>Verify your vote was counted, or audit an entire ballot from start to finish.</p>
</a>

<a href="{{ '/wallet-integration/' | relative_url }}" class="card">
<h3>Wallet Integration</h3>
<p>CIP-30/CIP-95 auth flows, multisig support, and building your own frontend.</p>
</a>

</div>
