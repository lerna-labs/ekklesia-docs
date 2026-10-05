---
"docs": patch
---

Raise the fast-uri override to 3.1.8 or later, which closes GHSA-hrr3-gc8f-f4qj,
and raise the brace-expansion overrides to 2.1.7 or later on the 2.x branch and
1.1.21 or later on the 1.x branch. All three are development-scope dependencies
of the spec linting and Postman generation tooling, so no published artifact or
site content changes.
