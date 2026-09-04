---
"docs": patch
---

Pin browserslist to 4.28.7 or later via an npm override. It is a transitive
dependency of Jest through Babel's compilation-target resolution, and floats on
a caret range that the lockfile had not yet picked up. This closes
GHSA-73wf-gq98-2v4g in the build tooling.
