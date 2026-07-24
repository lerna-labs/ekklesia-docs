---
layout: default
title: responderRole is server-derived
description: Wire-format change for POST /vote and POST /vote-and-register on the Hydra middleware. The responderRole field is no longer accepted from clients; it is derived from the voter's bech32 HRP before evidence is hashed.
---

# `responderRole` is now server-derived

**Effective:** Hydra middleware, all releases following the issue #1 fix.
**Affected endpoints:** `POST /vote`, `POST /vote-and-register`.
**Breakage:** None for well-behaved callers. Stale `responderRole` fields are
silently ignored; the server always emits the canonical value.

## What changed

Previously, the Hydra middleware accepted a `responderRole` string in the
request body of `POST /vote` and `POST /vote-and-register` and copied it
verbatim into the IPFS-pinned `VoteEvidence` object. That evidence is
`blake2b_256`-hashed into the on-chain `voteHash`, so a client-supplied
value became part of the immutable commitment.

The middleware now ignores any `responderRole` on the request body. It
derives the value from the bech32 HRP of `voterId` and writes that into
the evidence object before hashing.

The mapping (canonical, lowercase, three-role space):

| Bech32 HRP   | `responderRole` in evidence |
|--------------|-----------------------------|
| `drep`       | `drep`                      |
| `pool`       | `pool`                      |
| `calidus`    | `pool`                      |
| `stake`      | `stake`                     |
| `stake_test` | `stake`                     |

`addr` and `addr_test` (payment credentials) and CC identities have always
been rejected at the wire by the middleware and remain so.

## What downstream consumers need to do

### Vote-broker / backend integrators

- Stop sending `responderRole` on the wire to the Hydra middleware. Any
  value supplied is dropped at the route boundary; it never reaches the
  evidence object. There is no functional difference between sending the
  field and omitting it, but sending it is misleading to anyone reading
  HTTP traces.
- The shape of `VoteEvidence` is unchanged. `responderRole` is still a
  required field on the JSON pinned to IPFS — only the *source* of the
  value has changed (server-derived vs. client-supplied).
- The on-chain `voteHash` is `blake2b_256` of the canonical JSON of
  `VoteEvidence`. Auditors recomputing the hash should use the
  server-derived role value, which they can independently rederive from
  the bech32 HRP of `voterId` recorded in `ekklesia.credentialHrp`.

### Direct API users

If you've been hard-coding `responderRole: "DRep"` (mixed case) or any
other value in your request bodies, you can delete that field. The
canonical lowercase role names (`drep`, `pool`, `stake`) are derived for
you. Mixed-case variants from earlier API versions (`DRep`, `SPO`,
`Stakeholder`) were already non-canonical in the tally layer; the fix
makes them inexpressible at submission time as well.

### Auditors

- Tallies in `results.json` were already keyed on the HRP-derived role
  (`HRP_TO_ROLE[credentialHrp]` with `evidence.responderRole` only as a
  fallback). No `results.json` schema change.
- Evidence verification: `evidence.responderRole` is now guaranteed to
  agree with `evidence.ekklesia.credentialHrp` for any vote pinned after
  this change. A mismatch in older evidence indicates a vote pinned under
  the prior, vulnerable code path and should be treated as suspect.

## Why

`POST /vote` and `POST /vote-and-register` accept signed vote payloads
from any caller holding the Hydra API key. The signature proves control
of the voter credential, but it does not prove the role claim — the role
field was never part of the signed payload. Accepting it from the client
created a permanent, on-chain commitment to a value the voter never
signed for. Deriving from the bech32 HRP (which *is* part of the signed
payload, via `voterId`) closes that gap.

## Reference

- Issue: [ekklesia-hydra#1](https://github.com/Lerna-Labs/ekklesia-hydra/issues/1)
- Companion fix at the broker layer: ekklesia-backend#39 (tracked
  separately; the middleware fix alone is sufficient for the middleware
  surface, but until the broker fix lands, callers going through the
  broker may still produce mismatched evidence).
