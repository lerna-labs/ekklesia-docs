---
"docs": patch
---

Raise the fast-uri override to 3.1.8 or later, which closes GHSA-hrr3-gc8f-f4qj,
and raise the brace-expansion overrides to 2.1.7 or later on the 2.x branch and
1.1.21 or later on the 1.x branch. fast-uri is a transitive dependency of
openapi-to-postmanv2 (through ajv), used to generate the downloadable Postman
collections; both brace-expansion copies arrive only through Jest. All three are
development-scope dependencies, so no published artifact or site content
changes.
