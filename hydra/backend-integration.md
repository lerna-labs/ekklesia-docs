---
layout: default
title: Backend to Hydra Calls
description:
  What the Ekklesia backend sends to the Hydra middleware at ballot startup,
  voter login, vote submission, and results rollup, and what the middleware does
  with each call.
---

The Ekklesia backend never talks to a Hydra node directly. Every call goes to
the Hydra middleware, an Express service that owns the head, the admin wallet,
the vote cache, and IPFS pinning. This page lists each call the backend makes
for the four stages of a ballot: startup, login, vote submission, and rollup.
Endpoint parameters, response schemas, and error codes are in the middleware's
[OpenAPI specification](https://github.com/lerna-labs/ekklesia-hydra/blob/main/openapi.yaml);
this page covers only which calls the backend makes, when, and with what.

For the ballot stages themselves (prepare, start, vote, finalize, close,
settle), see [Hydra & Architecture]({{ '/hydra/' | relative_url }}).

## How the backend calls the middleware

- **One middleware instance per ballot.** The backend stores the middleware
  endpoint on the ballot and looks it up for every call. Only endpoints on the
  deployment's configured allowlist are used.
- **Authentication.** Every request carries an `x-api-key` header. The
  middleware rejects a missing or wrong key with `401 UNAUTHORIZED`. The backend
  holds one key per middleware instance.
- **Response envelope.** The middleware answers
  `{ status, data, code, message }`. The backend treats `status: "ERROR"` or a
  non-2xx HTTP status as a failure and otherwise uses `data`.
- **No retries on writes.** The backend retries only read requests (twice, with
  backoff). A `POST` is sent once, because `/prepare`, `/start`, and `/vote` are
  not idempotent. Long operations get long client timeouts: 5 minutes for
  `/prepare`, 12 minutes for `/start`, 16 minutes for `/settle/close`. `/vote`
  uses the 30 second default.

## 1. Startup

Two things are called startup, and they are different.

**The scheduled startup hook makes no Hydra call.** A backend cron runs every
ten minutes and picks up each ballot whose voting period begins within the next
ten minutes and which has not been started. It runs the ballot's configured
startup script and, if the script returns true, records `startupAt` on the
ballot. The script shipped in the backend only logs and returns true. A separate
one-minute cron then sets ballots with a recorded `startupAt` to `live` once
their voting period opens. Neither cron contacts the middleware.

**Opening the head is an administrator action.** The backend exposes
ballot-scoped admin routes, which require admin credentials, that pass through
to the middleware. The two that startup depends on are prepare and start.

### Prepare

The backend sends `POST /prepare` to the middleware instance chosen for the
ballot, forwarding the administrator's request body unchanged apart from the
endpoint selector. The body carries `namespace` and the `ballot` definition,
with optional `gasAmount`, `cip179`, and `resultsAddress`.

In the middleware, `/prepare` mints the (600) definition and (601) instance
tokens on Cardano L1 under a timelocked native script, pins the ballot
definition to IPFS, and submits the mint transaction. It returns the transaction
hash, policy ID, fingerprint, the two asset names, the ballot IPFS CID, the
timelock slot, and the UTxO to commit into the head.

The backend stores the returned values on the ballot (prepare transaction hash,
ballot CID, policy ID, asset names, fingerprint, timelock slot, commit UTxOs)
and marks the ballot as Hydra-sourced. These are what start needs.

### Start

The backend sends `POST /start`. Any of the fields below the administrator does
not supply are filled from the values stored at prepare:

| Field                                  | Source                    |
| -------------------------------------- | ------------------------- |
| `utxos` (`txHash`, `outputIndex` list) | commit UTxOs from prepare |
| `ballotPolicy`                         | policy ID from prepare    |
| `ballotToken`                          | (601) instance asset name |
| `ballotIpfsCid`                        | ballot CID from prepare   |
| `ballotId`                             | the backend ballot ID     |

The backend refuses locally, without calling the middleware, if `utxos`,
`ballotPolicy`, or `ballotToken` is still missing.

In the middleware, `/start` does the following in order:

1. Rejects the request with `409` if the head is already open, or if the staging
   directory still holds a finalized ballot's audit record.
2. Fetches the ballot definition from IPFS and validates it. If it cannot be
   fetched or fails validation, it refuses to open the head.
3. Clears any leftover vote cache and history from an aborted earlier session
   and waits for the head to reach Open.
4. Caches the ballot definition and identity (policy, token, ballot ID, and
   results address if given) for the voting and settlement routes.
5. Starts depositing the (601) token and its gas ADA into the head as a signed
   deposit, in the background, and returns immediately.

The response is `202` with `status: "OPENING"`, `ballotActive: false`, the
deposit status, and an estimated ready time. The deposit takes up to the head's
deposit period to mature, so the ballot is not accepting votes yet when `/start`
returns. `GET /health` reports `ballotActive: true` once it is. Until then,
`/vote` and `/register` answer `409 CONFLICT`.

After `/start` returns, the backend calls `GET /head-info`, stores the head ID
and head status on the ballot, and sets the ballot status to `live`. This
happens when the call returns, not when the deposit completes.

## 2. Login

At the end of a successful wallet login, for key-based and multisig voters
alike, the backend sends a request to the middleware's registration endpoint and
does not wait for the result. The login response to the voter is built without
it.

| Item           | Value                                                   |
| -------------- | ------------------------------------------------------- |
| Endpoint       | `POST /register`                                        |
| Authentication | `x-api-key`, from a deployment-wide setting (see below) |
| Payload        | `{ "userId": "<voter ID>" }`                            |

The login ping reads its URL and key from a single deployment-wide setting, not
from the per-ballot lookup described above, and is skipped if either is unset.

The middleware's `/register` is defined to mint the voter's in-head token. It
reads the field `voterId`, not `userId`. A request carrying only `userId` fails
the field check and is answered `400 MISSING_FIELDS` before any other check, so
the login ping does not register a voter in the head. The backend discards the
response.

What this means for voters: registration is not a login-time step. A voter's
in-head token is created by their first vote. `POST /vote` registers an
unregistered voter and records the first vote in one transaction, and the
backend always uses `/vote` rather than `/register`. Login also does not create
any authentication token in Hydra. The session token a voter receives at login
is issued and held by the backend alone.

## 3. Vote submission

A voter's submission passes through the backend's draft, signature, and submit
steps first. Once the package has its signature or, for a multisig voter, enough
signatures to satisfy the native script, the backend submits it. See the [Voting
API]({{ '/api/voting/' | relative_url }}) for those steps.

### What the backend sends

Before sending, the backend re-verifies every stored witness against the
package's own signing payload and, for multisig, that the native script is
satisfied. A package that fails is marked failed and is never sent.

| Item           | Value                                                                 |
| -------------- | --------------------------------------------------------------------- |
| Endpoint       | `POST /vote`                                                          |
| Authentication | `x-api-key` for the ballot's middleware instance                      |
| `voterId`      | the voter's bech32 ID                                                 |
| `ballotId`     | the backend ballot ID                                                 |
| `votes`        | the answers from the signed payload                                   |
| `signature`    | the voter's witness, described below                                  |
| `nonce`        | the package nonce, which must exceed the voter's last confirmed nonce |

The backend also includes a `responderRole` field. The middleware ignores it and
derives the role from the voter ID, as described in [responderRole is
server-derived]({{ '/hydra/responder-role-derivation/' | relative_url }}).

For a key-based voter, `signature` is the single COSE witness (`coseSign1Hex`,
`coseKeyHex`, `key`, `signature`), plus `calidusDeclaration` when a Calidus key
signed. For a multisig voter it is `nativeScript` and a `witnesses` array.

### What the middleware does

For one voter at a time (concurrent requests from the same voter are
serialized), the middleware:

1. Checks that the (601) deposit is ready, and that the voter's credential type
   is permitted by the ballot.
2. Validates the selections against the cached ballot definition.
3. Computes the blake2b-256 hash of the canonical signed payload (`ballotId`,
   `nonce`, `votes`) and verifies the voter's signature or native script
   witnesses against it.
4. Builds the vote evidence, hashes it to `voteHash`, and pins it to IPFS.
5. If the voter has no in-head token yet, builds one transaction that mints it
   and records the vote. Otherwise builds a vote update, which requires the
   nonce to exceed the current version.
6. Signs the transaction with the administrator key, queues it, and waits for
   the head to validate it.
7. Writes the evidence to the local vote cache and appends the voter's history.

### What comes back

On success the middleware returns `txHash`, `voteHash`, `ipfsCid`, `version`,
`tokenName`, and `registered` (true when this call created the voter's token).
The backend stores the transaction hash, IPFS CID, and vote hash on the vote
package, marks it `hydra-confirmed`, commits the nonce, and mirrors each answer
into a per-question vote record. A cron that runs every ten minutes repairs any
confirmed package whose mirror records are missing, for example after a process
restart between the two writes.

On any failure the backend marks the package failed and releases the nonce, so
the voter can submit again. Typical middleware errors are `400 INVALID_VOTE`,
`401 SIGNATURE_INVALID`, `403 INELIGIBLE_VOTER`, `409 CONFLICT` (nonce not
increased, or ballot not active yet), and `503` (IPFS unavailable).

## 4. Rollup

There are two kinds of rollup, and they use the middleware differently.

### Provisional tallies make no Hydra call

A cron that runs every ten minutes tallies each question that received votes in
the last twelve minutes. It reads the backend's own per-question vote records,
the ones mirrored at submission time, not the middleware. This applies to Hydra
ballots only when the ballot has provisional results enabled. Such tallies are
informational. A question that already has a final result is never overwritten.

### Final results come from the middleware

Closing a ballot is a sequence of administrator calls that the backend passes
through to the middleware, in this order:

| Step | Call                    | What the middleware does                                                                                                                                                          |
| ---- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `POST /settle/burn`     | Burns the voter tokens in the head. Repeated until the response reports `remaining` of 0.                                                                                         |
| 2    | `POST /settle/finalize` | Requires no voter tokens remain. Tallies, builds the merkle tree of evidence, pins the results and evidence to IPFS, and writes the results and merkle root into the (601) datum. |
| 3    | `POST /settle/close`    | Takes `closeToken`. Closes the head and fans out to L1, where the (601) token lands at the results address.                                                                       |

Neither body carries ballot identity; the middleware uses what `/start` cached.

After `/settle/finalize` returns, the backend:

1. Calls `GET /audit/full`, which returns every voter's evidence from the
   middleware's local disk (no IPFS reads).
2. Derives the per-question results, the per-voter-group results, and the
   participation counts from that evidence, and stores them as the final result,
   replacing any provisional one.
3. Stores the finalize response fields on the result: results hash, results CID,
   evidence directory CID, evidence merkle root, voter count, and excluded
   voters.
4. Sets the ballot status to `closed`, and refreshes the head ID and status from
   `GET /head-info`.

If the backend loses the finalize response (a timeout or dropped connection), it
can re-fetch it from the middleware with `GET /results`, which returns the same
payload byte for byte, and run the same steps. If `/audit/full` is unavailable
at that moment, the backend still stores the finalize response fields and defers
the tallies to that recovery step.

The final result is the one anchored on Cardano L1, so it is the one an auditor
verifies. See the [Technical Auditor
Guide]({{ '/audit/technical/' | relative_url }}).
