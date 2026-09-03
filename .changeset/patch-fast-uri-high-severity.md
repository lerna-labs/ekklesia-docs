---
"docs": patch
---

Pin fast-uri to 3.1.6 or later via an npm override. It is a transitive dependency of ajv, which openapi-to-postmanv2 uses to validate schemas while generating the downloadable Postman collections. This closes GHSA-4c8g-83qw-93j6, GHSA-v2hh-gcrm-f6hx, GHSA-7p8r-x3mc-p8w7, GHSA-q3j6-qgpj-74h6, GHSA-v39h-62p7-jpjc, GHSA-f65p-4m7j-42xc, and GHSA-jqff-g426-hqxp in the build tooling.
