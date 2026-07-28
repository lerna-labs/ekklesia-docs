---
layout: default
title: Security Audit
description:
  Findings from the independent security audit of the Ekklesia voting platform,
  and the remediation applied to each one.
---

The Ekklesia voting platform was subjected to an independent third-party
security audit in 2026. This page publishes the findings of that audit, the
disposition of each finding, and the remediation that was applied. It is
intended for anyone evaluating whether the platform is safe to run a real
election on, and for anyone reviewing the code who wants to know which parts
have already been scrutinised.

Nothing on this page is a summary written for marketing purposes. Where a
finding was contested, that is stated. Where a finding remains open, that is
stated too, with the reason.

## The engagement

| Field                | Value                                                                         |
| -------------------- | ----------------------------------------------------------------------------- |
| Auditor              | Amoor Family, LLC                                                             |
| Report title         | Ekklesia Security Audit: formal verification, property testing, and L1 replay |
| Report date          | 3 June 2026                                                                   |
| Engineering response | 18 June 2026                                                                  |
| Code under audit     | `ekklesia-hydra` at `f94fd10`, `ekklesia-backend` at `39234a8`                |

The audit was not a checklist review. It was built as four independent
verification layers, each capable of failing the system on its own:

- **A property-testing adversary suite.** Sixty-four executable properties
  driven by generated adversarial inputs, with fifteen dedicated adversary
  modules. Each reported defect shipped with a reproducible failing case.
- **Formal verification in Lean 4.** Ten universally quantified theorems over
  the pure-logic surface of the system: tally derivation, input validation,
  native-script satisfaction, and nonce handling.
- **A ledger conformance oracle.** CIP-129 round-trip and native-script
  conformance checked against the upstream Cardano reference encoders rather
  than against our own understanding of them.
- **An independently reimplemented ballot auditor.** A from-scratch verifier
  that replays the documented cryptographic checks against Cardano L1 and IPFS
  alone, without using any Ekklesia code.

The fourth layer matters most for a voting system. An auditor who reimplements
the verification path independently, and reaches the same answer, is evidence
that the published results can be checked by a third party who trusts none of
our software.

## Findings at a glance

The audit recorded sixteen findings.

| Severity | Count |
| -------- | ----- |
| Critical | 1     |
| High     | 9     |
| Medium   | 4     |
| Low      | 2     |

Three further items were raised during testing, re-investigated by the auditor,
and re-classified as not a defect. We agree with that re-classification and
added regression sentinels for all three so that a future refactor cannot
silently remove the behaviour that makes them safe.

Current disposition:

| Disposition                                                   | Findings                                                      |
| ------------------------------------------------------------- | ------------------------------------------------------------- |
| Accepted and remediated as recommended                        | F-003, F-005, F-006, F-007, F-009, F-010, F-012, F-013, F-015 |
| Accepted and remediated, fix diverges from the recommendation | F-001, F-002                                                  |
| Contested with evidence                                       | F-004, F-011 (partial)                                        |
| Open, deferred                                                | F-008, F-014, F-016                                           |
| Confirmed not a defect, regression sentinel added             | three items                                                   |

Thirteen of the sixteen findings are closed with a code change, a test that pins
the fix, and a merged pull request. The three that remain open are described in
full under [Open items](#open-items).

## Cross-cutting decision: protocol versioning

Two ballots had already settled on Cardano mainnet before the audit findings
were remediated: the CIWG ballot and the Cardano Budget Process 2026 ballot.

Several findings required changing how a vote is represented, hashed, or
identified. Applying those changes in place would have retroactively broken
replay of both settled ballots. Their evidence would no longer reconstruct,
their voter-token names would no longer decode, or their vote hashes would no
longer match. A voting system that quietly invalidates its own historical record
is not auditable, whatever its current code does.

Every representation-changing fix therefore shipped under a bumped protocol
version, `ekklesia/2.0`, with the previous path retained. Replay tooling selects
its verification path from the ballot's own declared version. The two settled
ballots keep their original version strings and verify byte for byte, unchanged,
today.

## Critical

### F-001: CIP-151 calidus credential header byte

**Finding.** The calidus credential prefix was `0x06`, deviating from CIP-151,
which specifies `0xa1`.

**Disposition.** Accepted as a real problem. Remediated, but not by changing the
byte.

Changing the prefix to `0xa1` would have made the token name conformant without
addressing what we found while investigating it. A voter token name is the
prefix followed by a hash of the credential. A pool cold key and a calidus hot
key hash to different values, so they already produce different token names
whatever the prefix byte is. The real problem was that `calidus` was a
first-class voter credential type at all: a client could submit a calidus
identifier and mint a second voter token alongside that same operator's pool
token, with both counting under the pool role and nothing deduplicating them.
One stake pool operator, two votes. The recommended byte change would have left
that open.

Our identity model is that a stake pool operator always votes as the pool, and
the calidus key is supplied only as a signing witness. We made the code enforce
that model. A calidus identifier is now rejected as a voter identity and
accepted only as a witness on a pool identity. One operator can hold at most one
voter token.

**Exposure on settled ballots.** Confirmed clear. Neither settled ballot
accepted a calidus voter identity.

## High

### F-002: credential-hash extraction handled only one credential type

Script-based credentials other than a script DRep were silently rejected,
because a one-byte header was stripped for only one of the several credential
encodings that carry one. The concrete victim was a script-based stake
credential: a legitimate voter who would have been turned away. Remediated with
a credential-hash extractor scoped to the genuinely script-capable credential
types, with non-script credentials returning an explicit rejection rather than
falling through silently.

### F-003: a malformed rating grid could reach the tally

Ballot definitions are fetched from IPFS when a voting session starts. That path
trusted the fetched definition without revalidating it. A malformed numeric grid
could therefore reach the tally enumerator, where a non-positive step size made
the enumeration loop non-terminating: finalisation would hang rather than fail.
Remediated in two places. The tally enumerator now validates its grid and raises
an error instead of looping, and the session-start path now fetches and
validates the ballot definition before opening or modifying any state, so a
malformed ballot is rejected at the door.

### F-004: write-ahead-log reconciliation used a prefix match

**Contested, with a hardening change applied anyway.**

We were not able to reproduce a reachable defect. The value being matched is
always a full-length transaction hash, and the delimiter appears only after it,
so the prefix match already required exact equality. Two distinct full hashes
cannot be prefixes of one another. The reported collision depends on a truncated
hash, which this codebase never produces. Separately, the queue entry model
carries no output index, so the exact-index form the report recommended would
have required data the entry does not have.

We made the intent explicit anyway, so the code no longer reads as a prefix
hack. Behaviour is unchanged.

We did find a different, lower-risk gap while investigating: a transaction that
landed but whose output was later consumed reconciles as not found and triggers
a resubmit, which then fails safely on spent inputs. It is recorded rather than
changed.

### F-005: ranked tally did not deduplicate a ranking

A ranked ballot listing the same option twice caused the pairwise preference
matrix to record an option as preferring itself, corrupting every result method
derived from that matrix. The vote submission path already rejected duplicate
rankings, but evidence retrieved out of band from IPFS reaches the tally
directly. Remediated by deduplicating each ranking once, preserving
first-occurrence order, so first preferences still count correctly and the
matrix diagonal is provably zero.

### F-006: vote hash canonicalisation diverged between components

The middleware and the API hashed the same vote evidence two different ways, so
identical evidence could produce two different hashes depending on which
component produced it. Remediated by moving both onto a single shared
canonicalisation library, with a cross-component contract test that pins the
exact expected hash for a shared test vector.

We went further than the finding asked. The signing payload is now canonicalised
before the ballot hash the voter signs is computed, and votes are stored and
submitted in canonical key order. Any third party implementing Ekklesia derives
the same expected hash for a given voter and selection set.

### F-007: evidence bundle shape drifted between components

The two components that publish vote evidence to IPFS emitted structurally
different bundles, so a replay auditor had to know which component produced an
object in order to parse it. Remediated on both sides. Both producers now emit
an identical bundle under `ekklesia/2.0`, with structural guards in the test
suite that fail if either producer reintroduces a retired version string or
drops a required field.

### F-008: CIP-179 poll method representation

**Open.** See [Open items](#open-items).

### F-014: fanout reproduction and value conservation

**Open.** See [Open items](#open-items).

### F-015: finalisation must be snapshot-confirmed before the session closes

Final results are written inside the Hydra head. Closing the head posts the
latest confirmed snapshot to L1. Settlement previously waited only for the
finalisation transaction to be accepted, not for it to be included in a
confirmed snapshot, so a close occurring in that window could publish a stale
result datum to L1. Remediated with an explicit confirmation gate: finalisation
now returns only once its result is in a confirmed snapshot, so any subsequent
close publishes the finalised result by construction. A timeout fails the
finalisation for operator retry rather than allowing a close on unconfirmed
state.

## Medium

### F-009: results endpoint error envelope

The auditor confirmed the existing behaviour is correct and does not leak
whether a ballot exists. We added a regression sentinel so a future refactor
cannot turn it into an error that does leak.

### F-010: unrecognised credential types were coerced rather than rejected

Role resolution fell back to a default role when it did not recognise a
credential type, so a credential with a missing type was silently counted as a
real DRep vote, and an unrecognised one could fall back to a role supplied in
the evidence itself. Remediated with fail-closed resolution: an unrecognised
type is rejected on the vote path, and in the tally it lands in an explicit
unknown bucket. It never lands in a real role, and never in a self-declared one.

### F-011: testnet credential type asymmetry

**Partially contested.** The report asked for testnet variants of two credential
types by analogy with a third. Those variants do not exist. Governance
credentials use the same prefix on every network, and only stake reward
addresses are network-tagged. The asymmetry is correct rather than a gap, and
the fail-closed resolver from F-010 rejects any such string anyway.

### F-016: single-operator liveness modelling

**Open.** See [Open items](#open-items).

## Low

### F-012: credential prefix naming

The constant name implied a literal encoding byte when the value is an internal
role marker inside the voter token name. Renamed exactly as recommended, values
unchanged.

### F-013: CIP-67 label registration

The on-chain token labels used by Ekklesia were not registered and could collide
with a future standard. Resolved by documenting the labels, datum schemas,
validation rules, and audit formats as a candidate Cardano Improvement Proposal,
submitted as
[cardano-foundation/CIPs PR 1207](https://github.com/cardano-foundation/CIPs/pull/1207).

## Findings from our own ballot audit

In parallel with the external engagement we ran a cryptographic replay over the
Cardano Budget Process 2026 ballot and a focused review of the multi-signature
signing path. That surfaced issues outside the external auditor's scope. Two
were Critical. We publish them here because a security page that reports only
the findings someone else caught is not an honest one.

### Co-signers were served the wrong value to sign (Critical, fixed)

For a voter using a multi-signature script, the API served co-signers the
evidence hash in place of the ballot hash they were supposed to sign. The two
signers therefore signed two different representations of the same vote, and
because the signature endpoint checked only key membership, the package was
stored and submitted without any signature ever being verified against the
message.

Remediated on three levels. The signed value is now always derived from the
stored signing payload. Each witness is verified when it is submitted, both that
it signed this vote's ballot hash and that the signature validates. And the
whole package is re-verified against the script before it is submitted, so an
unverifiable package cannot reach settlement even if an earlier check were
bypassed.

### Script witness signatures were never verified (Critical, fixed)

The middleware extracted each witness public key but never verified the
signature or the message it signed before counting that key toward the
multi-signature threshold. An M-of-N script could be satisfied by keys that
never signed anything. Remediated by verifying each witness signature and its
message before it counts toward the threshold. Forged, stale, and wrong-message
witnesses are now rejected.

### Multi-signature stored payload diverged from the signed message (High, fixed)

A consequence of the two issues above. Closed by the same fixes: a witness that
signed anything other than the recomputed ballot hash is now rejected at vote
time.

### Cached ballot identifier could be overwritten on restart (High, fixed)

A voting session that re-seeded its identity mid-ballot could fall back to a
default identifier at settlement, so every voter's signed ballot identifier
differed from the settled on-chain one. The effect was uniform rather than
selective, so it did not indicate tampering, but it broke the cross-check
between a vote and the ballot it belongs to. Remediated by rejecting a restart
of an already-open session and validating the fetched ballot before any state is
opened or cleared.

## Open items

Four items remain open. None is an active exploit in the current single-operator
deployment, and each is recorded here rather than quietly carried.

### F-008: CIP-179 poll method representation (High)

The middleware describes poll methods using URI strings, following the draft of
CIP-179 that was current when the code was written. CIP-179 was subsequently
finalised and merged on 23 June 2026, and the final standard specifies integer
tags rather than URI strings.

This is an interoperability gap, not a vulnerability. Ekklesia ballots verify
correctly against Ekklesia tooling and against an independent reimplementation
of the documented checks. What does not yet work is a generic CIP-179 client
reading an Ekklesia ballot's method tags without a translation layer. The
migration is scheduled under the `ekklesia/2.0` protocol version, and the
property suite carries a trip-wire test that fails until it is done.

### F-014: fanout reproduction and value conservation (High, defence in depth)

The audit modelled, but could not exercise against production, the requirement
that closing a Hydra head reproduces the pre-close state exactly and conserves
value. No defect was exposed. What is missing is an assertion, not a fix: the
replay tooling does not yet check the fanout transaction against the last
confirmed snapshot. Scheduled for the replay tooling and the formal model rather
than the middleware.

### F-016: single-operator liveness modelling (Medium, defence in depth)

The formal model covers safety properties but treats liveness under operator
fault as a deterministic skeleton rather than a property-based schedule. No
production change is indicated for a single-operator deployment. Recorded as a
formal-model extension.

### COSE hashed-header handling (Medium, accepted)

Neither the signature verification path nor the underlying SDK reads the CIP-8
`hashed` flag, so a wallet that chose to sign a hashed payload would be
rejected. We are leaving this open deliberately. The only value ever presented
for signing is a fixed-length hash, and every witness observed in production
signs it unhashed, so the path is not exercised. It is recorded so that it is
not forgotten if the signing target ever changes.

## Where the fixes live

Every remediation is a merged pull request in a public repository, with tests
that pin the fix.

| Component             | Repository                                                                      |
| --------------------- | ------------------------------------------------------------------------------- |
| Hydra middleware      | [lerna-labs/ekklesia-hydra](https://github.com/lerna-labs/ekklesia-hydra)       |
| Voting API            | [lerna-labs/ekklesia-backend](https://github.com/lerna-labs/ekklesia-backend)   |
| Voter web application | [lerna-labs/ekklesia-frontend](https://github.com/lerna-labs/ekklesia-frontend) |
| Shared library        | [lerna-labs/ekklesia-helpers](https://github.com/lerna-labs/ekklesia-helpers)   |

All four are released under the Apache License 2.0.

## Verifying this for yourself

You do not have to take any of the above on trust. The [Technical Auditor
Guide]({{ '/audit/technical/' | relative_url }}) documents the full verification
path against Cardano L1 and IPFS, using no Ekklesia software. The [Verify My
Vote]({{ '/audit/verify-my-vote/' | relative_url }}) guide covers the same
ground for an individual voter checking a single vote.

The strongest evidence in this audit is that someone else already did exactly
that, independently, and reached the same answer.
