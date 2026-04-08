---
layout: default
title: API Overview
description:
  Programmatic access to Ekklesia ballot data, vote submission, and proposal
  management.
---

Ekklesia exposes two primary APIs for integration:

<div class="card-grid">

<a href="{{ '/api/voting/' | relative_url }}" class="card">
<h3>Voting API</h3>
<p>Query ballots (current, upcoming, historical), fetch results, submit votes, and interact with the voter directory.</p>
</a>

<a href="{{ '/api/proposals/' | relative_url }}" class="card">
<h3>Proposals API</h3>
<p>Submit and query proposals, and interact with the pre-voting proposal feedback system.</p>
</a>

</div>

## General Notes

- Provisional results (e.g., estimated vote weighting) may be rolled up
  periodically and endpoints are cached. These are **strictly informational** —
  final tabulation of voter eligibility, voting power, and thresholds is the
  responsibility of the **voting authority** (the organization conducting the
  vote), not Ekklesia as the voting administrator. Excessive polling may result
  in temporary IP blacklisting.
- Authentication uses **CIP-8 message signing** — request a nonce, sign it with
  your wallet, and receive a JWT session token. This works with both CIP-30
  browser wallets and CLI tools like CardanoSigner.
- Endpoints may vary between Ekklesia instances. Always check the instance's
  base URL.
- API stability is improving but not yet guaranteed — integrate at your own
  discretion and pin to specific versions where possible.
