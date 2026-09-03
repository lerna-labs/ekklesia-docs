# docs

## 1.2.1

### Patch Changes

- 56cd12a: Pin fast-uri to 3.1.6 or later via an npm override. It is a
  transitive dependency of ajv, which openapi-to-postmanv2 uses to validate
  schemas while generating the downloadable Postman collections. This closes
  GHSA-4c8g-83qw-93j6, GHSA-v2hh-gcrm-f6hx, GHSA-7p8r-x3mc-p8w7,
  GHSA-q3j6-qgpj-74h6, GHSA-v39h-62p7-jpjc, GHSA-f65p-4m7j-42xc, and
  GHSA-jqff-g426-hqxp in the build tooling.
- 75d656e: Pin js-yaml to 4.3.1 or later on the 4.x branch and 3.15.1 or later
  on the 3.x branch, and lodash to 4.18.1 or later, via npm overrides. This
  closes GHSA-5p4m-2wfm-xmqj, GHSA-52cp-r559-cp3m, and GHSA-r5fr-rjxr-66jc in
  the build tooling used to lint the OpenAPI specs and generate the downloadable
  Postman collections.

## 1.2.0

### Minor Changes

- 7c260cc: Publish the findings of the independent security audit and the
  remediation applied to each one. The new page under Auditability records the
  structure of the engagement, the sixteen findings by severity, and the
  disposition of each, including the four where the fix diverges from the
  recommendation or the finding was contested with evidence. It also publishes
  the two Critical defects found by our own cryptographic replay of a settled
  mainnet ballot, which fell outside the external auditor's scope, and the four
  items that remain open, each with the reason it is open. The protocol
  versioning decision is explained where it belongs, alongside the findings that
  required it, since that is what allows the ballots settled under the previous
  version to keep verifying unchanged. Linked from the Auditability section of
  the navigation and from the auditability overview, next to the voter and
  technical auditor guides.

### Patch Changes

- 5b7dcff: Document the specVersion 2.0 canonical JSON rule and correct the
  pages that drifted from it. The technical audit guide now states which
  serialization each hashing phase uses, since canonical (sorted-key) JSON
  applies to the per-voter evidence envelopes but not to the question
  contentHash behind the on-chain ballot merkle root. It also records the two
  envelope guarantees that let an auditor implement the canonical form without a
  full RFC 8785 library: numeric values are always integers within IEEE-754
  double range, and object keys are always ASCII protocol field names. String
  values may be any UTF-8, and candidate labels never appear in an envelope. The
  authority guide no longer describes the pinned ballot JSON as canonicalized,
  which collided with the narrower meaning 2.0 gave that word, and the wallet
  integration guide notes that the signing payload is already in lexicographic
  order so both encodings agree.

## 1.1.0

### Minor Changes

- 4a3da83: Show the documentation version and build date in the site footer, and
  cut releases through an accumulating release pull request.
- 50856e1: Add the central issue templates, contributor and security policies,
  dependency automation, and changelog versioning for the documentation site.
- 822d1b2: Publish the site when a release is cut rather than on every merge, so
  what is live always matches a released version.

### Patch Changes

- 5fbe619: Route Hydra SDK issues to that project's own tracker rather than the
  central one.
- aef72a0: Teach the ballot auditor that specVersion 2.0 hashes vote evidence
  envelopes as canonical JSON. Step 6 now picks the envelope encoding from the
  ballot's declared specVersion instead of always serializing in insertion
  order, so 2.0 ballots verify while previously settled ballots keep verifying
  under the older encoding. When no version matches, the failure now reports
  whether the other encoding would have matched, so a future format change reads
  as a format change rather than as evidence tampering.
- 48b1751: Require a changelog entry on every change, including editorial fixes.
