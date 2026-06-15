---
layout: default
title: Voting API
description: Ekklesia core API for ballots, votes, results, and audit artifacts.
---

The Voting API is the primary integration surface for Ekklesia. The frontend is
a thin client around this API — anything the UI can do, you can do
programmatically.

## API Versions

The Voting API has two coexisting versions:

### v1 — Live (Hydra-backed)

The active surface for all new ballots. Votes are processed through the Hydra
broker pipeline and settled on-chain. v1 also publishes the audit artifacts
(per-proposal canonical content, archive bundle, certification state) and the
cross-source unified ballot listing.

- **Unified ballot listing** across all sources (Hydra + archived legacy)
- **Vote broker** — draft / sign / submit pipeline for Hydra-powered votes, with
  multisig support and rehydration
- **Results** — separate, poll-friendly endpoints for provisional + final
  tallies
- **Audit endpoints** — content blobs, downloadable archive bundle, and
  authority certification state
- **Public integrator surface** — API-key gated read-only access

Operational endpoints that talk directly to the Hydra head — ballot prepare /
start / settlement, ingestion, voting-power uploads, certification ingest — are
administrator-only and not part of the published API surface.

All endpoints are prefixed with `/api/v1/`. View the full [interactive
specification]({{ '/api/voting/spec/' | relative_url }}) or download the
[OpenAPI YAML]({{ '/api/voting/openapi.v1.yaml' | relative_url }}).

### v0 — Archival + Live Read

The legacy API surface. **Writes to ballot, proposal, vote, voter, transaction,
and dashboard resources return HTTP 410 Gone** with a pointer to the v1
equivalent. Read endpoints remain available for archived ballots, and the
**Session, Comments, and FAQs** endpoints continue to function on v0 — those
handle authentication and pre-vote feedback for both versions.

All endpoints are prefixed with `/api/v0/`. View the full [v0 interactive
specification]({{ '/api/voting/spec-v0/' | relative_url }}) or download the [v0
OpenAPI YAML]({{ '/api/voting/openapi.v0.yaml' | relative_url }}).

## Authentication

The published surface uses two authentication methods:

| Method                            | Used By     | Endpoints                            |
| --------------------------------- | ----------- | ------------------------------------ |
| **JWT session** (CIP-8 signing)   | Voters      | `/api/v0/session`, `/api/v1/votes/*` |
| **API key** (Bearer or x-api-key) | Integrators | `/api/v1/public/*`                   |

Voter authentication uses **CIP-8 message signing**: request a nonce, sign with
your wallet or keys, receive a JWT session cookie. Standard and multisig
(script-address) voters share a single set of session endpoints — include
`scriptAddress` in the request body for multisig. See the [Wallet Integration
guide]({{ '/wallet-integration/' | relative_url }}) for the full handshake.

API keys are scoped (`read:ballots`, `read:results`, etc.) and rate-limited per
key. Contact the voting authority for a key.

## Dual-id resolution

Every path parameter that names a ballot, proposal, or question (`:id`,
`:ballotId`, `:proposalId`, `:qid`) accepts either the canonical Mongo `_id`
**or** the corresponding upstream external id
(`proposalSource.externalBallotId`, `externalProposal.id`). Both resolve to
the same canonical row. When a request resolves via an external id,
responses carry a top-level `canonical` field and a
`Link: <…>; rel="canonical"` header so search engines and integrators only
index one URL per resource. Ambiguous external matches return HTTP 409 with
code `ID_COLLISION` and the list of candidate `_id`s.

## Query-string hygiene

Known scalar query keys (`status`, `voterType`, `search`, `page`, `limit`,
`source`, …) must be strings. Object-shaped values (NoSQL operator
injection — `?status[$ne]=null`) and array-shaped values (duplicate params
— `?status=live&status=closed`) return HTTP 400 `BAD_INPUT`. Free-text
`search` and `voterType` values are regex-escaped, so unbalanced patterns
like `?search=(` are matched as literal substrings rather than throwing.

## v1 Endpoints

### Health & Config

| Method | Path             | Description                              |
| ------ | ---------------- | ---------------------------------------- |
| `GET`  | `/api/v1/health` | Version + liveness probe                 |
| `GET`  | `/api/v1/config` | Explorer + IPFS gateway + network for UI |

`/config` is public and unauthenticated — frontends and third-party integrators
read it to render explorer / IPFS links without hardcoding a network.

### Unified Ballots

| Method | Path                  | Description                                 |
| ------ | --------------------- | ------------------------------------------- |
| `GET`  | `/api/v1/ballots`     | List ballots (all sources: hydra + legacy)  |
| `GET`  | `/api/v1/ballots/:id` | Ballot detail (includes `source` + `hydra`) |

Each ballot row includes a `source` field (`"legacy"` or `"hydra"`) and a
`hydra` sub-object with head status (null for legacy ballots). Responses use
status-aware caching: closed = 3600 s, live = 120 s, upcoming = 30 s. The list
response is cached for 60 s.

### Proposals

| Method | Path                            | Description                                               |
| ------ | ------------------------------- | --------------------------------------------------------- |
| `GET`  | `/api/v1/proposals/:proposalId` | Single proposal + slim parent-ballot projection           |
| `GET`  | `/api/v1/proposals/ballot/:id`  | Facet-driven sort/filter listing for a ballot's proposals |

Sort and filter keys must be declared on `Ballot.facets[]`. Multi-value enum
filters take comma-separated values; OR within a facet, AND across facets.
Facets are frozen once a ballot goes live, so the filter UI can safely cache the
facet list for the ballot's lifetime.

### Results

Results are separated from ballot detail for efficient polling.

| Method | Path                                   | Auth   | Description                   |
| ------ | -------------------------------------- | ------ | ----------------------------- |
| `GET`  | `/api/v1/results/ballot/:ballotId`     | Public | All Result rows for a ballot  |
| `GET`  | `/api/v1/results/proposal/:proposalId` | Public | Single proposal result        |
| `GET`  | `/api/v1/ballots/:id/certified`        | Public | Authority certification state |

Result rows carry `source: "provisional" | "final"` and the Hydra settlement
artifacts (`hydraResultsCid`, `hydraResultsHash`, `hydraEvidenceMerkleRoot`,
`hydraTotalVoters`, `hydraExcludedVoters`) once the ballot has been finalized.

`/ballots/:id/certified` distinguishes certified-by-authority results from
provisional Hydra-final tallies. When a `CertifiedSnapshot` is active, results
are flagged "Certified at version N by &lt;authority&gt;"; otherwise they're
labelled "Provisional".

### Audit Artifacts

| Method | Path                                         | Description                                                              |
| ------ | -------------------------------------------- | ------------------------------------------------------------------------ |
| `GET`  | `/api/v1/ballots/:id/questions/:qid/content` | Per-proposal canonical content bytes (chain-of-custody hash target)      |
| `GET`  | `/api/v1/ballots/:id/archive`                | Full audit bundle (ballot + proposals + manifest + README), downloadable |

Both endpoints are public and unauthenticated by design — long-term auditability
requires no gate. The chain of custody runs:

```
on-chain (601) datum → ekklesia.merkleRoot
  → IPFS-pinned ballot JSON (covers BallotQuestion.contentHash[n])
    → per-proposal content blob (questions/:qid/content)
```

The `/archive` endpoint returns one JSON file with a per-file hash manifest
(`blake2b_256` + `sha256`) and a README containing the verification recipe. It's
served with `Content-Disposition: attachment` so browsers download instead of
preview. See the [Technical Auditor
Guide]({{ '/audit/technical/' | relative_url }}) for the full verification flow.

### Vote Broker (Live Ballots)

The vote submission flow is a draft → sign → submit pipeline. Drafts are
**idempotent on (voter, ballot)** — re-clicking `/draft` with matching
selections returns the existing package; with different selections (and no
collected signatures) it updates in place.

**Step 1 — Draft.** Reserve / resume a nonce and receive the canonical signing
payload.

```
POST /api/v1/votes/:ballotId/draft
Body: { votes: [...], nativeScript?, calidusDeclaration? }
```

`responderRole` is derived server-side from the authenticated voter's
bech32 HRP and is no longer accepted on the request body — any
client-supplied value is ignored.

Returns:
`{ status, package: { id, status, nonce }, signingPayload, signingPayloadHex, merkleRoot, signedPayloadJson, prelimVoteHash, multisig }`.

**Step 2 — Sign.** The voter signs the `merkleRoot` (64-char hex string) using
CIP-8 message signing to produce a COSE witness. Sign the hex characters
verbatim — Hydra's verifier compares the COSE payload ASCII against this exact
string.

**Step 3 — Submit.** Send the witness to the broker.

```
POST /api/v1/votes/:ballotId/signature
Body: { packageId, witness: { coseSign1Hex, coseKeyHex, key, signature } }
```

The broker validates, aggregates (for multisig), and submits to Hydra when the
signature threshold is met.

| Method   | Path                                         | Description                                            |
| -------- | -------------------------------------------- | ------------------------------------------------------ |
| `POST`   | `/api/v1/votes/:ballotId/draft`              | Reserve/resume nonce, return signing payload           |
| `POST`   | `/api/v1/votes/:ballotId/signature`          | Append a signature; submits when threshold met         |
| `POST`   | `/api/v1/votes/:ballotId/submit`             | Manual retry for `awaiting-submission`                 |
| `GET`    | `/api/v1/votes/:ballotId/mine`               | Rehydrate voter state (confirmed + in-flight packages) |
| `GET`    | `/api/v1/votes/:ballotId/packages`           | List voter's vote packages on this ballot              |
| `GET`    | `/api/v1/votes/:ballotId/package/:packageId` | Current package state                                  |
| `DELETE` | `/api/v1/votes/:ballotId/package/:packageId` | Abandon an in-flight package; releases the nonce       |

<div class="callout callout-warning">
<strong>Hydra replaces; it does not merge.</strong> Every submitted vote
payload is treated as the voter's <em>complete</em> final state. To amend
or add votes, rehydrate from <code>/mine</code>'s <code>confirmed.votes</code>,
let the user edit the selection set, and send the COMPLETE ballot to
<code>/draft</code>. Removing a prior vote is simply omitting it.
</div>

### Public Integrator Surface

Read-only API for third-party tools. Requires an API key.

| Method | Path                                  | Description      |
| ------ | ------------------------------------- | ---------------- |
| `GET`  | `/api/v1/public/ballots`              | List ballots     |
| `GET`  | `/api/v1/public/ballots/:id`          | Ballot detail    |
| `GET`  | `/api/v1/public/results/ballot/:id`   | Ballot results   |
| `GET`  | `/api/v1/public/results/proposal/:id` | Proposal results |

Authenticate with `Authorization: Bearer <key>` or `x-api-key: <key>`. Keys are
scoped and rate-limited per key.

### Operational Endpoints (Not Public)

Endpoints that talk directly to the Hydra head — ballot prepare / start, the
stepped settlement sequence, head and queue observability, inspection helpers —
together with ballot ingestion, voting-power snapshot uploads, and authority
certification ingest are operated by voting administrators. They are not part of
the published API surface and are intentionally omitted from this documentation.
Instance operators can integrate against them out-of-band; if you are running a
voting authority and need access, contact the instance administrator.

## v0 Endpoints (Archival + Live Read)

<div class="callout callout-warning">
<strong>v0 writes are disabled.</strong> POST, PUT, PATCH, and DELETE
requests to v0 ballot, proposal, vote, voter, transaction, and dashboard
resources return HTTP 410 with a migration pointer to v1. Session,
Comments, and FAQs continue to accept writes.
</div>

| Method   | Path                            | Status       | Description                            |
| -------- | ------------------------------- | ------------ | -------------------------------------- |
| `GET`    | `/api/v0/ballots`               | Read-only    | List archived ballots                  |
| `GET`    | `/api/v0/ballots/:id`           | Read-only    | Archived ballot detail                 |
| `GET`    | `/api/v0/proposals/:id`         | Read-only    | Archived proposal + voting stats       |
| `GET`    | `/api/v0/voters`                | Read-only    | Archived voter directory               |
| `POST`   | `/api/v0/session`               | Live         | Request authentication nonce           |
| `PUT`    | `/api/v0/session`               | Live         | Verify signature; receive JWT          |
| `GET`    | `/api/v0/session`               | Live         | Validate current session               |
| `DELETE` | `/api/v0/session`               | Live         | Logout                                 |
| `GET`    | `/api/v0/comments`              | Live         | List top-level comments for a proposal |
| `POST`   | `/api/v0/comments`              | Live         | Create a comment on a live proposal    |
| `GET`    | `/api/v0/comments/:id`          | Live         | Single comment                         |
| `PUT`    | `/api/v0/comments/:id`          | Live         | Edit own comment (15-minute window)    |
| `GET`    | `/api/v0/comments/:id/replies`  | Live         | Paginated replies                      |
| `POST`   | `/api/v0/comments/:id/like`     | Live         | Toggle like on a comment               |
| `PUT`    | `/api/v0/comments/:id/withdraw` | Live (admin) | Admin withdrawal of a comment          |
| `GET`    | `/api/v0/faqs`                  | Live         | Live FAQs (search + filter)            |

The full v0 surface — including dashboard, transactions, and proposals lookup —
lives in the [v0 specification]({{ '/api/voting/spec-v0/' | relative_url }}).

## Health Probes

The voting backend exposes liveness probes at the **server root**, not under
`/api/vN`. Mounted at: `/health`, `/health/health`, `/health/db`. The v1 surface
also exposes `/api/v1/health` for v1-specific liveness.
