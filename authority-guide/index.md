---
layout: default
title: Voting Authority Guide
description:
  Operating the Ekklesia voting platform. A manual for authorities running
  ballots end-to-end.
---

This guide is for **voting authorities**, meaning the people running the
software, authoring ballots, opening Hydra heads, and certifying results.
Voters and integrators have their own guides:

- Voters: [Getting Started]({{ '/getting-started/' | relative_url }})
- Integrators / third-party tooling: [API Reference]({{ '/api/' | relative_url }})

If you are running an Ekklesia instance for a working group, a treasury vote,
an SPO poll, or a community signal, this is the manual that walks the full
ballot lifecycle, from authoring through on-chain settlement and audit
publication.

## What a voting authority is

The **voting authority** is the organization or individual operating an
Ekklesia instance and conducting a specific ballot. The authority is
responsible for:

1. **Defining the ballot.** Questions, voting window, eligible voter groups,
   vote types per question.
2. **Preparing on-chain anchors.** Minting the (600) reference and (601)
   instance tokens that anchor the ballot to Cardano L1.
3. **Operating the Hydra head.** Opening, monitoring, and closing the L2
   state channel where votes are cast.
4. **Voter eligibility and power.** Ekklesia treats every voter as one voter
   casting one vote. Eligibility filters and stake-weighted tabulation are
   the authority's responsibility, not the platform's.
5. **Certifying the final results.** Applying any authority-specific
   tabulation (weighting, thresholds, exclusions) to the cryptographic
   record produced by the head.
6. **Publishing audit artifacts.** Pinning the evidence directory to IPFS
   and ensuring the on-chain proof remains independently verifiable.

Ekklesia provides the cryptographic infrastructure. The authority provides
the **legitimacy and political context** that turns a stack of signed
messages into a binding decision.

## The ballot lifecycle, end-to-end

Every Ekklesia ballot moves through the same six phases. Each phase has a
public artifact that ends up on-chain or in IPFS, so the lifecycle is fully
auditable from the outside.

### 1. Author

The authority drafts the ballot in the [Proposal Module]({{ '/proposals/' |
relative_url }}) (or directly via the v1 ballot ingestion path). A ballot
contains:

- **Title, description, and namespace.** The namespace is a stable
  identifier for the voting program (e.g.,
  `vote.ekklesia.preprod.ciwg.rss-v2`).
- **Voting window.** Open and close timestamps in UTC.
- **Eligible voter groups.** DReps, SPOs, address holders, stake
  credentials, token / NFT holders, or any combination.
- **Questions / proposals.** One or more, each with its own
  [vote type]({{ '/vote-types/' | relative_url }}) (binary, single-choice,
  multi-choice, range, ranked, weighted, or Likert).
- **Facets.** Sort and filter keys exposed to the proposal listing UI.
  Frozen once the ballot goes live.

The full ballot JSON is **canonicalized** (deterministic key ordering,
normalized whitespace) and pinned to IPFS. The IPFS CID becomes the
immutable content address of the ballot's text. Once pinned, the ballot's
questions cannot be edited without producing a different CID, breaking the
on-chain commitment.

### 2. Prepare: mint (600) and (601) on Cardano L1

The authority mints two tokens on L1 under a single ballot policy:

| Token | Purpose                                                              |
| ----- | -------------------------------------------------------------------- |
| (600) | **Reference token.** Inline datum carries `ballotCid`, `merkleRoot` over the canonical ballot, the voting window, the namespace, and the authority address. Stays at the authority address for the entire lifecycle. |
| (601) | **Instance token.** Committed into the Hydra head at start; returns to the authority at fanout carrying the final settlement datum. |

This pair is the on-chain fingerprint of the ballot. The (600)'s
`merkleRoot` is the commitment to the ballot text. Anyone with a Cardano
data provider key (Blockfrost, Koios, Maestro, `cardano-cli`) can re-fetch
the ballot from IPFS and re-hash it to confirm the on-chain commitment.

### 3. Start: open the Hydra head

The authority opens a Hydra head dedicated to this ballot. The head's
opening sequence is three L1 transactions that anyone can inspect on a
Cardano explorer:

1. **Init.** Mints the `HydraHeadV1` control token and the participant
   token for the authority's payment credential.
2. **Commit.** Commits the (601) instance token plus gas UTxOs into the
   head.
3. **CollectCom.** Head transitions to **Open**; voting can begin.

Ekklesia heads are designed to be **single-party**: the authority is the
sole Hydra participant. This is intentional. The authority is the neutral
party operating the voting infrastructure, not a co-signer of voter
ballots. Voter signatures are independent COSE_Sign1 witnesses inside the
head's ledger, not Hydra participant signatures.

### 4. Vote

While the head is open:

- Voters authenticate against the authority's instance with their wallet
  (CIP-30 / CIP-95 / CIP-151 calidus key).
- The voter signs a canonical payload over their selections; the broker
  pipeline (`/api/v1/votes/:ballotId/draft` → `/signature` → `/submit`)
  aggregates signatures and submits the vote as a transaction inside the
  head.
- Each vote replaces the voter's previous vote in full. Hydra does not
  merge votes; every submission is treated as the voter's complete final
  state.

The authority's job during the voting window is **operational, not
editorial**: monitor head state, watch for stuck transactions, resolve
voter support issues. The authority **cannot forge or alter votes**;
every vote is signed by the voter's own keys and replayable from the
head's ledger.

Provisional results may be polled and rolled up periodically (typically
every 10 minutes), but these are strictly informational. Final tabulation
is bound to the on-chain proof produced at fanout.

### 5. Finalize, Close, Settle

When the voting window closes, the authority moves the head through
settlement:

1. **Finalize inside the head.** Aggregate all signed votes, build the
   per-voter merkle tree, write the results datum into the (601) token,
   and burn voter-issued tokens back to zero.
2. **Close.** Submit the L1 close transaction; the head transitions to
   **Closed** and starts the contestation period.
3. **Fanout.** Submit the L1 fanout transaction; the (601) returns to the
   authority address carrying the final inline datum:
   - `ballotId`: internal identifier.
   - `resultsHash`: `blake2b-256` of the canonical `results.json`.
   - `evidenceCid`: IPFS content address of the full evidence directory.
   - `evidenceMerkleRoot`: root of the per-voter merkle tree.
   - `schemaVersion`.

After fanout, the cryptographic record is **frozen on-chain**. Nothing the
authority does after this point can change what is committed.

### 6. Certify and publish

The authority publishes:

- The full evidence directory pinned to IPFS, addressed by the
  `evidenceCid` in the (601) datum.
- The provisional Hydra-final results (raw, one-voter-one-vote).
- An **authority-certified results snapshot** with any tabulation rules
  applied (stake weighting, threshold tests, role-based exclusion). The
  certified snapshot is versioned and signed by the authority address;
  reviewers can compare provisional vs certified to see exactly where the
  authority's tabulation rules diverged from the raw cryptographic record.

The certification step is the seam between **what was cast** (controlled
by cryptography) and **what counted** (controlled by the authority's
political mandate). Both are on the public record.

## Operational responsibilities

### Voting power and eligibility

Ekklesia stores **every cast vote** but does not apply voting power or
eligibility filtering at the vote-acceptance layer. This is deliberate.
The platform's job is to record signed votes faithfully; the authority's
job is to decide which votes count and how heavily. The authority defines
eligibility (e.g., "DRep registered as of epoch N", "SPO with > 0 active
stake") and uploads voting-power snapshots out-of-band; the certification
step applies them when producing the certified snapshot.

If you delegate voting power to an external snapshot provider, document
which provider and which snapshot block. Auditors will compare your
certified tabulation against your declared rules.

### Public integrator access

Third parties (block explorers, governance dashboards, vote-tracking
tools) can integrate against the **read-only public surface** under
`/api/v1/public/*`. Authentication uses scoped, rate-limited API keys.
The authority issues keys to integrators on request. Typical scopes are
`read:ballots` and `read:results`.

The public surface intentionally exposes only what an external observer
needs: ballot listings, ballot detail, results. It does not expose the
operational endpoints (head control, queue management, certification
ingest); those are kept under administrative auth and are not part of
the published API.

### Audit posture

Every ballot the authority runs should be independently auditable
end-to-end with no Ekklesia-operated service in the trust loop. The audit
chain of custody is:

```
on-chain (601) datum → ekklesia.merkleRoot
  → IPFS-pinned ballot JSON (covers BallotQuestion.contentHash[n])
    → per-proposal content blob (questions/:qid/content)
```

The authority is responsible for:

- Keeping the IPFS pins live for the lifetime of the audit window.
- Publishing the [Technical Auditor Guide]({{ '/audit/technical/' |
  relative_url }}) link or equivalent for each ballot.
- Surfacing the on-chain (600) and (601) UTxOs and the IPFS CIDs in the
  ballot's results page so reviewers don't have to dig.

The single-file Python auditor (`audit_ballot.py`, [download
here]({{ '/downloads/' | relative_url }})) verifies all 13 cryptographic
checks against L1 + IPFS alone. Authorities are encouraged to run it as
a self-check immediately after fanout and to publish the script's output
alongside the certified results.

### Security and key custody

The authority's wallet keys hold:

- The ballot policy (mint/burn authority for (600) and (601)).
- The Hydra participant keys.
- The certification signing key.

These keys are not separable inside the current architecture. Losing the
wallet means losing the ability to certify, and a compromised wallet means
an attacker can mint forged ballot tokens or spoof certified snapshots.
Treat them as production-critical: hardware wallet, multisig, or HSM as
appropriate to the stakes of the ballot.

The authority **cannot forge votes**, regardless of key custody. Voter
signatures are independent of authority keys. But the authority **can**
publish a malicious ballot, an inflated voter list, or a fraudulent
certification. The cryptographic record provides independent verification
for everything _voters_ control; the authority's discipline provides
everything else.

## Pre-flight checklist

Before opening a ballot to voters, confirm:

- Ballot JSON pinned to IPFS; CID resolves from at least two independent
  gateways.
- (600) and (601) minted; both inline datums decode against the documented
  Plutus shape.
- Hydra head reaches **Open** state cleanly (Init, Commit, CollectCom all
  confirmed on L1).
- API keys issued to any expected integrators; rate limits set.
- Voting power snapshot collected (if applicable) and stored alongside the
  ballot's audit bundle.
- The ballot's results page links the (600) UTxO, (601) UTxO, `ballotCid`,
  and the auditor script.
- Disaster-recovery plan: head doesn't open, authority key is unavailable,
  or a vote-storm overruns the queue. Who decides what?

## Further reading

- [Hydra & Architecture]({{ '/hydra/' | relative_url }}): the why and how
  of Hydra-backed voting.
- [Vote Types]({{ '/vote-types/' | relative_url }}): the seven supported
  voting mechanisms and their validation rules.
- [Voting API v1]({{ '/api/voting/' | relative_url }}): the integrator
  surface this guide refers to.
- [Auditability]({{ '/audit/' | relative_url }}): the verification model
  voters and reviewers use.
- [Wallet Integration]({{ '/wallet-integration/' | relative_url }}): CIP-8,
  CIP-30, CIP-95, and CIP-151 signing flows.
