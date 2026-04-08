---
layout: default
title: Proposal Module
description: How proposals are submitted, reviewed, and voted on in Ekklesia.
---

The Proposal Module is a self-contained component for managing proposal
submission and feedback cycles. It has its own API and frontend, and can be
deployed independently of the main voting platform.

## Proposal Lifecycle

Proposals move through the following states:

1. **Draft** — Proposer is still editing; not visible to the public
2. **Live** — Submitted and visible; open for feedback and review
3. **Withdrawn (by proposer)** — Proposer has pulled the proposal; requires a
   reason and may include a note
4. **Withdrawn (by admin)** — Admin has removed the proposal; requires a reason
   and may include a note

## Vote Cycles

Proposals are organized into **vote cycles** (funding cycles) with defined time
windows:

- **Submission window** — When proposers can submit or edit proposals
- **Feedback period** — When DReps and reviewers can comment and provide
  feedback
- **Review period** — Final review before voting begins

## Roles

| Role         | Capabilities                                       |
| ------------ | -------------------------------------------------- |
| **Proposer** | Create, edit, submit proposals during open windows |
| **DRep**     | View, comment, and review during feedback periods  |
| **SPO**      | View, comment, and review during feedback periods  |
| **Admin**    | Oversee and moderate proposals and comments        |
| **Public**   | View live proposals (no authentication required)   |

## API

The Proposal Module exposes its own REST API for programmatic access. See the
[Proposal Module API]({{ '/api/proposals/' | relative_url }}) reference for
endpoint documentation.
