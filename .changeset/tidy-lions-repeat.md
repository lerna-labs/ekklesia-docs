---
"docs": patch
---

Document the specVersion 2.0 canonical JSON rule and correct the pages that
drifted from it. The technical audit guide now states which serialization each
hashing phase uses, since canonical (sorted-key) JSON applies to the per-voter
evidence envelopes but not to the question contentHash behind the on-chain
ballot merkle root. It also records the two envelope guarantees that let an
auditor implement the canonical form without a full RFC 8785 library: numeric
values are always integers within IEEE-754 double range, and object keys are
always ASCII protocol field names. String values may be any UTF-8, and
candidate labels never appear in an envelope. The authority guide no longer
describes the pinned ballot JSON as canonicalized, which collided with the
narrower meaning 2.0 gave that word, and the wallet integration guide notes
that the signing payload is already in lexicographic order so both encodings
agree.
