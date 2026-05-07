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
> a ballot. This is distinct from proposals in the [Proposal > > > > > > > > >
> Module]({{ '/proposals/' | relative_url }}), which manages the submission and
> review process before something reaches a ballot.

## Vote Types

Ekklesia supports seven voting mechanisms. The Hydra validation layer enforces
the rules for each type — frontends decide how the options are presented to
voters, but the on-the-wire shape and the validation rules are fixed.

The canonical method names used throughout this page (`binary`, `single-choice`,
`multi-choice`, `range`, `ranked`, `weighted`, `likert`) are the values the
Hydra middleware sees. The Proposal Module's authoring API uses a slightly
different surface (`choice`, `scale`, `budget`, …) which the backend resolves to
canonical Hydra methods at ballot-prepare time. See [Authoring
aliases](#authoring-aliases) below.

### Binary

The simplest vote type — a yes/no/abstain question.

- Voter selects exactly one option
- Standard options are Yes, No, and Abstain
- Functionally a single-choice with fixed options
- **Selection shape:** `number[]` of length 1 (the chosen option value)

### Single-Choice

Pick exactly one option from any set of choices.

- Voter selects exactly one option from the available list
- Options are defined per question with a label and integer value
- **Selection shape:** `number[]` of length 1

### Multi-Choice

Select multiple options within defined bounds.

- Voters may select multiple options
- Selection count must fall between `minSelections` and `maxSelections`
- No duplicate selections allowed
- **Selection shape:** `number[]` of distinct option values

### Range

Submit a numeric value within a defined range.

- Voter provides a single integer value
- Defined by `valueRange: { min, max, step? }` — `step` defaults to 1
- Value must lie on the arithmetic grid `{ min, min+step, …, max }`, and
  `(max − min) % step === 0` is enforced when the ballot is prepared
- Useful for a single overall scoring / rating / numeric input
- **Selection shape:** `number[]` of length 1

### Ranked

Order options by preference.

- Voters rank options in order of preference (array position 0 = first
  preference, position 1 = second, …)
- Must rank exactly `rankCount` options (defaults to all). For example, a
  question may require ranking exactly 3 out of 15 candidates
- No duplicate entries allowed
- Tally emits **first-preference counts** plus the full **pairwise preference
  matrix** — Borda, Condorcet, Schulze, IRV, Ranked Pairs, etc. are all
  computable downstream from this raw record without re-reading evidence
- **Selection shape:** `number[]` of option values in preference order

### Weighted

Distribute a point budget across options.

- Voters assign a weight (non-negative integer) to each option they want to
  fund
- All weights must sum to exactly the defined `budget`
- No duplicate option entries
- Useful for allocation decisions where voters distribute limited resources
  across choices
- Tally emits per-option `totalPoints` and `voterCount` (number of ballots
  with a non-zero allocation to that option)
- **Selection shape:** `SelectionEntry[]` — each entry is `{ option, value }`,
  where `value` is the points allocated to that option

### Likert

Rate every option independently on a discrete integer scale.

- Defined by `ratingRange: { min, max, step? }` — `step` defaults to 1
- Every option must receive **exactly one integer rating** on the grid
  `{ min, min+step, …, max }`. Ratings outside the grid (including non-integer
  values, values off the step grid, or duplicates / missing options) are
  rejected by Hydra at vote-validation time
- Distinct from **Range** (one numeric value across the whole question) and
  from **Weighted** (allocations that must sum to a budget — Likert ratings are
  independent and unbounded by a sum)
- Tally emits per-option `count` plus a `distribution` histogram zero-filled
  across the full rating grid; mean / median / mode are deliberately left to
  downstream consumers
- **Selection shape:** `SelectionEntry[]` — one `{ option, value }` per option
  on the question, where `value` is the rating

## Abstention

Every method allows the voter to abstain on a per-question basis by submitting
`{ questionId, abstain: true }` instead of a `selection`. Abstainers do **not**
contribute to any tally aggregate; they are surfaced separately as
`abstainedByRole` counts on the question result.

A question may opt out of abstention by setting `requireAnswer: true`, in
which case `abstain: true` is rejected and a `selection` must be present.
This is orthogonal to having an "Abstain" option among `options` — the
latter is a regular selection that shows up in per-option counts.

## Storage and tabulation

All vote types share the same ballot structure and are validated at the
Hydra layer.

Each ballot is signed by the voter as a `SignedVotePayload` —
`{ ballotId, nonce, votes: VoteSelection[] }` — and the canonical evidence
bundle is pinned to IPFS, with its blake2b_256 hash anchored on-chain through
the voter token's UTxO chain. The selection shape per method (above) determines
how `votes[].selection` is interpreted. See [Auditability]({{ '/audit/' |
relative_url }}) for the full evidence model and verification flow.

Tabulation runs after the head finalizes. Hydra emits **raw cryptographic
counts only** — per-option counts, per-value distribution histograms,
pairwise preference matrices, per-option point totals, per-option rating
distributions. Stake / role weighting, eligibility filtering, and any
opinionated "winner" computation (Borda scores, Condorcet winners, ranked-
choice elimination rounds, etc.) are **deliberately not** part of the
on-chain or IPFS results — those are downstream interpretations applied by
the voting authority on top of the raw evidence.

Results are bucketed by **role** (`drep`, `pool`, `stake`) on each question,
plus a `"raw"` aggregate across roles. Role-specific weighting modes
(`CredentialBased` / `StakeBased` / `PledgeBased`) live on the ballot
definition; they instruct downstream consumers how to weight, but do not
modify the raw counts that Hydra publishes.

## Authoring aliases

The Proposal Module exposes a slightly different naming surface to ballot
authors. The backend translates each alias to a canonical Hydra method when it
prepares the ballot for the head:

| Authoring `voteType` | Hydra `method` | Notes                                                                                        |
| -------------------- | -------------- | -------------------------------------------------------------------------------------------- |
| `choice`             | `binary` (2 options) or `single-choice` (≥3 options) | Selection shape is identical for both.                                 |
| `multi-choice`       | `multi-choice` | Honors `minSelections` / `maxSelections`.                                                    |
| `budget`             | `multi-choice` | Knapsack: backend additionally enforces Σ `option.cost` ≤ `voterBudget` at submission time. Hydra itself only enforces count bounds. |
| `weighted`           | `weighted`     | `voterBudget` becomes Hydra's `budget`.                                                      |
| `ranked`             | `ranked`       | Defaults `rankCount` to `options.length`.                                                    |
| `scale`              | `range`        | `voteIncrement` becomes the `step` on `valueRange`.                                          |
| `likert`             | `likert`       | `ratingRange` is passed through unchanged.                                                   |

For an auditor verifying tallies, the authoring alias is informational only —
the on-chain commitments and Hydra-validated rules always reference the
canonical method.

See the [Hydra & Architecture]({{ '/hydra/' | relative_url }}) section for
details on how validation works inside the state channel, and the
[Auditability]({{ '/audit/' | relative_url }}) section for the per-method tally
shapes emitted to the final results object.
