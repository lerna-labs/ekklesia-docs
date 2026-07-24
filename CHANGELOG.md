# docs

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
