---
layout: default
title: Voting API
description: Ekklesia core API for ballots, votes, proposals, and voter data.
---

The Voting API is the primary integration surface for Ekklesia. The frontend is
a thin client around this API — anything the UI can do, you can do
programmatically.

## Base URL

Each Ekklesia instance has its own API base. All endpoints are prefixed with
`/api/v0/`.

## Authentication

Most read endpoints are public. Write operations (submitting votes) require
authentication:

1. `POST /api/v0/session` — Request a challenge nonce (provide signer address)
2. Sign the nonce using **CIP-8 message signing** with your wallet or keys
3. `PUT /api/v0/session` — Submit the signature to receive a JWT session cookie

See the [Wallet Integration guide]({{ '/wallet-integration/' | relative_url }})
for implementation details.

## Endpoints

_Detailed endpoint documentation coming soon._

### Session

| Method | Path              | Description                           |
| ------ | ----------------- | ------------------------------------- |
| `POST` | `/api/v0/session` | Request auth nonce (provide address)  |
| `PUT`  | `/api/v0/session` | Verify signature and receive JWT      |
| `GET`  | `/api/v0/session` | Check current session (authenticated) |

### Ballots

| Method | Path                  | Description                         |
| ------ | --------------------- | ----------------------------------- |
| `GET`  | `/api/v0/ballots`     | List all ballots (filter by status) |
| `GET`  | `/api/v0/ballots/:id` | Get ballot details                  |

### Proposals

| Method | Path                    | Description                 |
| ------ | ----------------------- | --------------------------- |
| `GET`  | `/api/v0/proposals`     | List proposals for a ballot |
| `GET`  | `/api/v0/proposals/:id` | Get proposal details        |

### Votes

| Method | Path            | Description                     |
| ------ | --------------- | ------------------------------- |
| `POST` | `/api/v0/votes` | Submit a vote (authenticated)   |
| `GET`  | `/api/v0/votes` | Get votes for a ballot/proposal |

### Voters

| Method | Path                 | Description                      |
| ------ | -------------------- | -------------------------------- |
| `GET`  | `/api/v0/voters`     | Voter directory listing          |
| `GET`  | `/api/v0/voters/:id` | Voter profile and voting history |
