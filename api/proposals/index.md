---
layout: default
title: Proposals API
description: API for proposal submission, querying, and pre-voting feedback.
---

The Proposals API is an independent API that manages the proposal lifecycle —
submission, feedback, and review — separately from the [Voting
API]({{ '/api/voting/' | relative_url }}).

## Base URL

The Proposals API runs on its own instance. All endpoints are prefixed with
`/api/v0/`.

## Authentication

Same signing flow as the Voting API:

1. `POST /api/v0/session` — Request a challenge nonce (provide signer address)
2. Sign the nonce using **CIP-8 message signing** with your wallet or keys
3. `PUT /api/v0/session` — Submit the signature to receive a JWT session

## Interactive Specification

View the full interactive API specification with request/response schemas,
examples, and try-it-out functionality:

**[Proposals API Specification]({{ '/api/proposals/spec/' | relative_url }})**

You can also download the [OpenAPI
YAML]({{ '/api/proposals/openapi.yaml' | relative_url }}) directly.

## Endpoints

### Session

| Method | Path              | Description                           |
| ------ | ----------------- | ------------------------------------- |
| `POST` | `/api/v0/session` | Request auth nonce (provide address)  |
| `PUT`  | `/api/v0/session` | Verify signature and receive JWT      |
| `GET`  | `/api/v0/session` | Check current session (authenticated) |

### Proposals

| Method | Path                    | Description                                   |
| ------ | ----------------------- | --------------------------------------------- |
| `GET`  | `/api/v0/proposals`     | List proposals (filterable by status, cycle)  |
| `GET`  | `/api/v0/proposals/:id` | Get proposal details                          |
| `POST` | `/api/v0/proposals`     | Create a new proposal (authenticated)         |
| `PUT`  | `/api/v0/proposals/:id` | Update a proposal (authenticated, owner only) |

### Vote Cycles

| Method | Path                | Description       |
| ------ | ------------------- | ----------------- |
| `GET`  | `/api/v0/votes`     | List vote cycles  |
| `GET`  | `/api/v0/votes/:id` | Get cycle details |

### Comments

| Method | Path               | Description                   |
| ------ | ------------------ | ----------------------------- |
| `GET`  | `/api/v0/comments` | List comments for a proposal  |
| `POST` | `/api/v0/comments` | Add a comment (authenticated) |
