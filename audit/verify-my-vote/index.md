---
layout: default
title: Verify My Vote
description: How to confirm your vote was included in the final ballot results.
---

After a ballot closes and results are finalized, you can independently verify
that your vote was counted correctly.

## What You'll Need

- Your **voter identifier** (e.g., `stake1...`, `drep1...`, or `pool1...`)
- The **ballot ID** of the vote you want to verify

## How Verification Works

When a ballot is finalized, Ekklesia constructs a **merkle tree** containing
every valid vote. The **merkle root** — a single hash that represents all votes
— is committed to Cardano L1.

To verify your vote, you check that your specific vote can be proven to exist
within that merkle tree. This is called a **merkle inclusion proof**.

<div class="callout callout-info">
<strong>What this proves:</strong> Your exact vote (choices, signature) is part of the dataset that produced the on-chain result. It has not been altered, omitted, or fabricated.
</div>

## Step-by-Step Verification

_Verification tooling documentation coming soon._

## Why Final Results May Differ From Preliminary

During a live ballot, provisional results may be displayed periodically as a
convenience. These are **strictly informational**.

Ekklesia tabulates the cryptographic record of who voted and how. The
application of **voting power, voter eligibility, and thresholds** is the
responsibility of the **voting authority** — the organization conducting the
vote. These factors are applied to the auditable results produced by Ekklesia,
not by Ekklesia itself.

Final published results may differ from provisional displays once the voting
authority applies their eligibility and weighting criteria.
