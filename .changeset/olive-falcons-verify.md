---
"docs": patch
---

Teach the ballot auditor that specVersion 2.0 hashes vote evidence envelopes
as canonical JSON. Step 6 now picks the envelope encoding from the ballot's
declared specVersion instead of always serializing in insertion order, so
2.0 ballots verify while previously settled ballots keep verifying under the
older encoding. When no version matches, the failure now reports whether the
other encoding would have matched, so a future format change reads as a
format change rather than as evidence tampering.
