---
---

Ran the repository's Prettier formatter over the markdown tree so the committed
source matches what the formatter produces, and `npm run fmt:check` now passes.
The release build already runs the writing form of the formatter, so the
published site was reformatted at build time while the checked-in source stayed
unformatted; this brings the two back in sync. No prose content changed.
