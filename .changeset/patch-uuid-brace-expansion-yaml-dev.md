---
"docs": patch
---

Pin uuid to 11.1.1 or later, brace-expansion to 2.1.4 or later on the 2.x branch
and 1.1.18 or later on the 1.x branch, and yaml to 1.10.3 or later, via npm
overrides. uuid and yaml are transitive dependencies of openapi-to-postmanv2,
used to validate the OpenAPI specs and generate the downloadable Postman
collections; brace-expansion reaches the tree twice through Jest, once via glob
on the 2.x branch and once via test-exclude on the 1.x branch, and each branch
needed its own override to stay unmerged. This closes GHSA-w5hq-g745-h8pq,
GHSA-rgw5-rvv9-x895, GHSA-mh99-v99m-4gvg, and GHSA-48c2-rrv3-qjmp in the build
tooling. All four packages are development-scope dependencies used only while
linting specs and generating downloads, so no published artifact or site content
changes.
