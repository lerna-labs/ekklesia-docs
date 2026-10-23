---
layout: default
title: Compatibility
description:
  The component versions the Ekklesia integration tests have run together.
---

## What this table means

Each row lists a component version and the commit it was built from. A set is
the group of components that ran together, and the date is the day the set was
tested. The tested components are the backend, the proposal module, the frontend
and the Hydra middleware.

The integration tests start each component from the stated commit and run the
components together. A passing run means that set was tested together. It does
not describe any particular deployment, and it says nothing about components
that are not listed. A version that does not appear here has not been tested as
part of a set.

## Tested sets

<!-- compatibility-table:start -->

| Tested on  | Component        | Version | Commit         |
| ---------- | ---------------- | ------- | -------------- |
| 2026-10-23 | Backend          | 1.1.0   | `d0716de6bf40` |
| 2026-10-23 | Proposal module  | 1.6.3   | `07252ed905b0` |
| 2026-10-23 | Frontend         | 1.0.2   | `ac156302c31e` |
| 2026-10-23 | Hydra middleware | 1.1.2   | `f5ae92cfb29b` |

<!-- compatibility-table:end -->

The commit column shows up to the first 12 characters of the commit.

## Machine-readable data

The same sets are published as
[compatibility.json]({{ '/compatibility/compatibility.json' | relative_url }}),
described by
[compatibility.schema.json]({{ '/compatibility/compatibility.schema.json' | relative_url }}).
Versions are exact release versions, never ranges, and `testedOn` is a calendar
date. The table above is checked against this file on every change.
