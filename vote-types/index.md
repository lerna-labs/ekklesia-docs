---
layout: default
title: Vote Types
description:
  The different voting mechanisms supported by Ekklesia and their validation
  rules.
---

## Terminology

Before diving into vote types, it helps to understand how Ekklesia structures
things:

- **Vote** (Proposal Module) — The outer wrapper containing all proposals under
  consideration for a voting stage
- **Ballot** (Voting Module) — The votable unit presented to voters, containing
  one or more questions
- **Question / Proposal** — An individual item on a ballot. These terms are
  interchangeable within the voting module. Each question can have a **different
  vote type**

So a single ballot might contain a binary yes/no question alongside a weighted
allocation question — the vote type is set per question, not per ballot.

> **Note:** "Proposal" in the voting module refers to an individual question on
> a ballot. This is distinct from proposals in the [Proposal
> Module]({{ '/proposals/' | relative_url }}), which manages the submission and
> review process before something reaches a ballot.

## Vote Types

Ekklesia supports six voting mechanisms. The Hydra validation layer enforces the
rules for each type. It is up to frontends how they display the options to
voters.

### Binary

The simplest vote type — a yes/no/abstain question.

- Voter selects exactly one option
- Standard options are Yes, No, and Abstain
- Functionally a single-choice with fixed options

### Single-Choice

Pick exactly one option from any set of choices.

- Voter selects exactly one option from the available list
- Options are defined per question with a label and value

### Multi-Choice

Select multiple options within defined bounds.

- Voters may select multiple options
- Selection count must fall between `minSelections` and `maxSelections`
- No duplicate selections allowed

### Range

Submit a numeric value within a defined range.

- Voter provides a single integer value
- Value must fall between the question's defined `min` and `max`
- Useful for scoring, rating, or any numeric input within bounds

### Ranked

Order options by preference.

- Voters rank options in order of preference (array position = rank)
- Must rank exactly `rankCount` options (defaults to all). For example, a
  question may require ranking exactly 3 out of 15 candidates
- No duplicate entries allowed
- Can be used for ranked-choice tallying with elimination rounds

### Weighted

Distribute a point budget across options.

- Voters assign a weight (integer, non-negative) to each option
- All weights must sum to exactly the defined `budget`
- No duplicate option entries
- Useful for allocation decisions where voters distribute limited resources
  across choices

---

All vote types share the same ballot structure and are validated at the Hydra
layer. See the [Hydra & Architecture]({{ '/hydra/' | relative_url }}) section
for details on how validation works inside the state channel.
