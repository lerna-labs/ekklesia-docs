---
layout: default
title: System Flowcharts
description:
  How the Ekklesia services call each other, how a ballot moves from import to
  settlement, where voting power comes from, and how a vote reaches the Hydra
  head.
mermaid: true
---

These diagrams describe what the Ekklesia code does today. They cover the
services and how they call each other, the ballot lifecycle including the
backend startup scripts, the places where snapshot data and live chain data are
used, and the path of a single vote from a wallet to the Hydra head and on to
the results.

Request and response payloads are not described here. For what the backend sends
to the Hydra middleware at each stage, see [Hydra &
Architecture]({{ '/hydra/' | relative_url }}).

## Components

The voting site is a static SvelteKit app that the backend serves. The backend
is the only service the browser talks to for voting. It keeps its state in
MongoDB, looks up voter eligibility and voting power on Koios, and drives the
Hydra middleware over HTTP. The middleware owns the Hydra head and everything
that touches it.

```mermaid
flowchart TB
  voter["Voter wallet<br/>CIP-30 and CIP-95"]
  admin["Voting authority<br/>admin session"]
  pm["Proposal module<br/>separate service"]
  koios["Koios"]
  bf["Blockfrost"]
  l1["Cardano L1"]

  subgraph site["Voting site"]
    fe["Frontend<br/>SvelteKit static app"]
    be["Backend<br/>Express API"]
    jobs["Scheduled jobs<br/>every 1 and 10 minutes"]
    db[("MongoDB")]
  end

  subgraph hydra["Hydra side"]
    mw["Hydra middleware"]
    node["Hydra node<br/>the head"]
    trp["TRP<br/>transaction resolver"]
    ipfs["IPFS"]
  end

  voter -->|"signs login challenge<br/>and vote payload"| fe
  fe -->|"API v0 and v1"| be
  be -.->|"serves the built app"| fe
  fe -.->|"link out only"| pm
  admin -->|"ballot import and<br/>lifecycle calls"| be
  be --> db
  jobs --> db
  jobs -->|"startup scripts"| koios
  be -->|"eligibility and<br/>voting power lookups"| koios
  be -.->|"fallback for stake<br/>account lookups"| bf
  be -->|"HTTP, per-ballot endpoint"| mw
  mw -->|"hydra-sdk<br/>HTTP and WebSocket"| node
  mw --> trp
  mw -->|"pin ballot and evidence"| ipfs
  mw -->|"L1 reads and submits"| bf
  node <-->|"open, deposit,<br/>close, fanout"| l1
```

Solid lines are calls made on every ballot. Dotted lines are conditional or
informational: the backend serves the built frontend files, the frontend only
links to the proposal module, and the Blockfrost fallback applies only to stake
account lookups when Koios fails with a network error, a 5xx, or a 429 and a
Blockfrost project is configured.

Two libraries are shared across the services:

| Library                        | Used by                                    | For                                                                                                                         |
| ------------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `@lerna-labs/ekklesia-helpers` | Backend, Hydra middleware, proposal module | Server bootstrap and canonical JSON (backend), canonical JSON (middleware), validation and deposit checks (proposal module) |
| `@lerna-labs/hydra-sdk`        | Hydra middleware                           | Hydra node HTTP and WebSocket client, IPFS client, disk cache, signature verification, native scripts                       |

## Ballot status

A ballot has three user-facing statuses. Voting writes are gated on the ballot's
voting window rather than on the status, so a ballot that has not yet been
flipped to `closed` still refuses votes after its end time.

```mermaid
flowchart LR
  stImp(["import"]) --> stUp["upcoming"]
  stUp -->|"admin start, or 1-minute job after<br/>votePeriodStart when startup has run"| stLive["live"]
  stLive -->|"1-minute job after votePeriodEnd,<br/>or settle finalize, or results recover"| stClosed["closed"]
```

Importing a ballot again is refused once its status is `live` or `closed`.

## Ballot lifecycle

The lifecycle runs on three drivers: the voting authority calling lifecycle
operations through the backend, the two scheduled jobs, and the voters.

```mermaid
flowchart TD
  subgraph before["Before voting"]
    imp["Import compiled ballot<br/>admin upload or API-key client"]
    store["Ballot and proposals stored as upcoming<br/>startup, validation and rollup script names saved"]
    prep["Prepare<br/>middleware mints the 600 and 601 tokens,<br/>pins the ballot to IPFS, sets a timelock<br/>at the voting window open slot"]
    imp --> store --> prep
  end

  subgraph startup["Startup, 10-minute job"]
    pick{"votePeriodStart within the next<br/>10 minutes and startupAt empty?"}
    run["Run the ballot's startup script"]
    mark["Set startupAt"]
    pick -->|"yes"| run --> mark
  end

  subgraph open["Opening"]
    start["Start<br/>middleware opens the head and deposits the 601 token"]
    live1["Backend marks the ballot live<br/>when start returns"]
    live2["1-minute job marks it live<br/>if votePeriodStart has passed and startupAt is set"]
    start --> live1
  end

  subgraph voting["While voting is open"]
    login["Voter logs in and views the ballot"]
    vote["Voter drafts, signs and submits votes"]
    tens["10-minute job: mirror reconcile,<br/>provisional tally, voting power snapshot"]
  end

  subgraph after["After votePeriodEnd"]
    close1["1-minute job sets status closed"]
    rollup["10-minute job calls the rollup script<br/>for ballots that ended in the last 10 minutes"]
    settle["Settle<br/>burn voter tokens, finalize results, close the head"]
    final["Final results written from the head evidence"]
    cert["Optional authority certification"]
    close1 --> rollup
    settle --> final --> cert
  end

  store --> pick
  prep --> start
  mark --> live2
  live1 --> login
  live2 --> login
  login --> vote
  vote --> tens
  tens --> close1
  close1 --> settle
```

Rules the code enforces:

- Prepare mints under a timelocked policy that expires at the slot where the
  voting window opens, so it has to run before the window opens.
- The startup job only considers ballots whose voting period starts within the
  next ten minutes and whose `startupAt` is empty. A ballot whose startup script
  does not return `true` keeps `startupAt` empty. A Koios error inside any of
  the Koios-backed startup scripts ends the whole job run.
- Start and the startup script are independent. Start flips the status to `live`
  on its own. Without it, the 1-minute job flips the status once the voting
  period has begun and `startupAt` is set.
- Start returns before the 601 deposit finishes. The middleware answers vote
  requests with a conflict until its health report shows the ballot active.
- The 10-minute job calls the rollup script for ballots that ended in the last
  ten minutes and have no `resultTxHash`. The code marks this stage as not yet
  live.
- Settle is a stepped sequence: burn until nothing remains, finalize, then
  close. Finalize flips the status to `closed` and writes the final results.
- Certification is an optional authority step that re-weights the final tallies
  from an authority-supplied snapshot.

### What the scheduled jobs do

```mermaid
flowchart LR
  subgraph one["1-minute job"]
    a1["Set live ballots past votePeriodEnd to closed"]
    a2["Set upcoming ballots past votePeriodStart to live<br/>if startupAt is set"]
    a3["Mark stale vote packages abandoned<br/>and release their nonce<br/>60 minutes by default"]
    a1 --> a2 --> a3
  end

  subgraph ten["10-minute job"]
    b1["Run startup scripts"]
    b2["Reconcile vote mirrors"]
    b3["Aggregate provisional tallies"]
    b4["Refresh voting power snapshots"]
    b5["Backfill voter names"]
    b6["Rollup stage"]
    b1 --> b2 --> b3 --> b4 --> b5 --> b6
  end
```

## Where voting power comes from

This is where snapshot data and live chain data meet. Three things matter: when
the chain is read, where the result is stored, and which stored copy each
consumer reads.

Each ballot names its scripts. A ballot has a startup script, a voter validation
script and a rollup script, and each is a file in the backend's `config`
directory. The defaults are `startupBallot.js`, `voterValidationAlwaysTrue.js`
and `rollupBallot.js`.

```mermaid
flowchart TB
  koios[("Koios")]
  su["Startup script<br/>once, before the window opens"]
  vs["Validation script<br/>login, ballot view, draft"]
  uc[("UserCache<br/>validated flag, voting power, group")]
  job["Snapshot refresh<br/>10-minute job"]
  vps[("VoterPowerSnapshot")]
  upload["Authority voting power upload"]
  cert["Authority certification"]

  gate["Eligibility gate at draft"]
  tally["Tally weights<br/>provisional and final"]
  totals["Ballot totals<br/>and participation"]

  koios -->|"pool and DRep lists, read live at startup"| su
  su -->|"upsert validated rows"| uc
  koios -->|"per voter, live, only if the row is<br/>older than 8 hours and the ballot is live"| vs
  vs -->|"upsert"| uc
  uc --> gate
  uc --> tally
  uc -->|"every current script reads UserCache"| job
  job -->|"source: snapshot"| vps
  upload -->|"source: uploaded, the job stops<br/>touching the ballot"| vps
  vps --> totals
  uc -.->|"fallback when no snapshot row"| totals
  cert -->|"authority snapshot replaces<br/>these weights in final tallies"| tally
```

### Startup scripts

A startup script runs once, in the 10-minute job, for ballots that start within
the next ten minutes. The data it reads from Koios is live at that moment and is
written to the `UserCache` collection, which makes it a point-in-time copy for
the rest of the ballot.

| Script                        | Reads                                                    | Writes to `UserCache`                                                                                                                    |
| ----------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `startupBallot.js`            | Nothing. It logs and returns `true`.                     | Nothing                                                                                                                                  |
| `startupPledgeBasedVoting.js` | Koios pool list and pool info                            | One validated row per pool whose live pledge is at least its pledge, power is live pledge                                                |
| `startupStakeBasedVoting.js`  | Koios pool list and pool info                            | One validated row per pool, power is active stake                                                                                        |
| `startupIncentiveVote.js`     | Koios pool list and pool info, and every registered DRep | Pools whose live pledge is at least their pledge, power is live pledge, group `pool`; every DRep, power is the DRep amount, group `drep` |

### Voter validation scripts

A validation script decides whether a voter is eligible and what their power is.
The first group below reads only what is already in `UserCache`. The second
group reads live chain data for a single voter when the cached row is missing or
older than 8 hours, and only while the ballot status is `live`. Otherwise they
return the cached answer, or reject the voter when there is none.

| Script                               | Source                                                                                                                              | Voting power                                                                    |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `voterValidationAlwaysTrue.js`       | `UserCache`, no chain data. Validates any voter on first call.                                                                      | Whatever `UserCache` holds                                                      |
| `voterValidationSnapshot.js`         | `UserCache`, a validated row must exist                                                                                             | Whatever `UserCache` holds                                                      |
| `voterValidationStake.js`            | Re-exports `voterValidationSnapshot.js`                                                                                             | Whatever `UserCache` holds                                                      |
| `voterValidationAlwaysFalse.js`      | None. Rejects every voter.                                                                                                          | None                                                                            |
| `voterValidationDReps.js`            | Koios DRep info, live                                                                                                               | DRep amount                                                                     |
| `voterValidationPoolsPledge.js`      | Koios pool info, live                                                                                                               | Live pledge, if it is at least the pledge                                       |
| `voterValidationPoolsStake.js`       | Koios pool info, live                                                                                                               | Active stake                                                                    |
| `voterValidationPoolsVotingPower.js` | Koios pool info, live                                                                                                               | Pool voting power                                                               |
| `voterValidationStakeholder.js`      | Koios account info, Blockfrost fallback, live                                                                                       | Total account balance. Eligibility also applies the ballot's stake requirements |
| `voterValidationByCredential.js`     | Routes by voter credential prefix to the DRep, pool pledge or stakeholder script, after checking the ballot's declared voter groups | As the script it routes to                                                      |

What this means in practice:

- A ballot that pairs a startup script with a live validation script, such as
  `startupPledgeBasedVoting.js` with `voterValidationPoolsPledge.js`, starts
  from the startup copy of voting power. Each voter's row is replaced with a
  live lookup the next time their row is older than 8 hours and a validation
  call reaches the script. At draft time, a voter with a cached row already
  marked validated is accepted without a refresh, and the script is called only
  when the row is missing or not validated.
- A ballot with `startupBallot.js` and a live validation script, such as
  `voterValidationDReps.js`, has no startup copy at all. Every voter's power is
  looked up on demand and cached.
- Tally weights, in both the provisional and the final tally, come from
  `UserCache`. A voter with no `UserCache` row is weighted as 1 in both.
- Ballot totals and participation come from `VoterPowerSnapshot` first and fall
  back to `UserCache`. Each snapshot refresh runs the ballot's script
  `computePerVoterPower`, which in every current script reads the validated
  `UserCache` rows, so the refresh copies `UserCache` into `VoterPowerSnapshot`.
  An authority upload writes `VoterPowerSnapshot` directly and the refresh then
  skips the ballot.
- The ballot's `votingPowerSource` is `snapshot` by default. When no snapshot
  rows exist yet, the totals are computed once from the script, which reads
  `UserCache`. With `uploaded`, the script is never called for totals.

## Vote path

A vote goes from the wallet to the frontend, then to the backend, which holds a
draft and collects the signature, and then to the Hydra middleware, which
validates, pins and submits it to the head. Login comes first.

```mermaid
sequenceDiagram
  autonumber
  participant W as Wallet
  participant F as Frontend
  participant B as Backend
  participant M as MongoDB
  participant K as Koios
  participant H as Hydra middleware
  participant I as IPFS
  participant T as TRP
  participant N as Hydra node

  Note over W,B: Login
  F->>B: POST /api/v0/session with the voter address
  B->>M: store a nonce
  B-->>F: challenge
  F->>W: signData on the challenge
  W-->>F: COSE signature and key
  F->>B: PUT /api/v0/session
  B->>M: consume the nonce, upsert the user
  B-->>F: session token set as a cookie

  Note over F,B: Draft
  F->>B: POST /api/v1/votes/:ballotId/draft
  B->>B: check voting window, validate selections, derive role from credential prefix
  B->>M: read the voter's UserCache row
  opt no validated row
    B->>K: validation script lookup
    B->>M: write UserCache row
  end
  B->>M: reserve a nonce, store the vote package
  B-->>F: signing payload and merkle root

  Note over F,N: Signature and submission
  F->>W: signData on the merkle root
  W-->>F: COSE signature and key
  F->>B: POST /api/v1/votes/:ballotId/signature
  B->>B: verify the witness against the merkle root
  B->>H: vote
  H->>H: validate against the cached ballot, check credential type, verify signature
  H->>I: pin the vote evidence
  H->>T: resolve the register or cast-vote transaction
  H->>N: submit the signed transaction through the queue worker
  N-->>H: transaction valid
  H-->>B: transaction hash, vote hash, evidence CID, version
  B->>M: package hydra-confirmed, commit nonce, mirror Vote rows
  B-->>F: package state
```

Multisig voters collect several witnesses first. The backend submits to the
middleware only when the native script threshold is met, and until then it
answers each signature request with the collected state. The backend also offers
a submit call to retry a package that is waiting for submission.

Voting power is not part of the vote. The head records signed vote evidence, and
the backend applies voting power to it when tallying.

## Tally and settlement

Provisional tallies come from the backend's own copy of the votes. Final tallies
come from the head's evidence after settlement.

```mermaid
flowchart TD
  subgraph backend["Backend"]
    mirror["Vote rows mirrored from confirmed packages"]
    recon["10-minute job: reconcile mirrors<br/>for confirmed packages missing Vote rows"]
    prov["10-minute job: provisional tally<br/>Hydra ballots only if provisionalResultsEnabled<br/>weights from UserCache"]
    resp["Result stored, source provisional"]
    audit["Fetch the audit bundle from the middleware"]
    derive["Derive tallies from the evidence<br/>weights from UserCache"]
    finalres["Result stored, source final<br/>overwrites provisional<br/>status set to closed"]
    cert["Optional certification<br/>Result source certified"]
    mirror --> prov
    recon --> prov
    prov --> resp
    audit --> derive --> finalres --> cert
  end

  subgraph middleware["Hydra middleware and head"]
    burn["Settle burn<br/>burn voter tokens, save the pre-burn ledger<br/>repeat until none remain"]
    fin["Settle finalize<br/>check each voter's evidence against its hash,<br/>tally, pin evidence and results to IPFS,<br/>write the results into the 601 datum in the head"]
    wait["Wait for the head snapshot that confirms the write"]
    close["Settle close<br/>close, contestation, fanout"]
    l1["601 token with the results on L1"]
    burn --> fin --> wait --> close --> l1
  end

  fin -->|"after finalize returns"| audit
```

Final results overwrite provisional results, and a proposal that already has a
`final` or `certified` result is skipped by the provisional tally. If the
finalize response is lost, a recover call fetches the stored response from the
middleware and writes the same results.
