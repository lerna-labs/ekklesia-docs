# VoteType Scale

Basically a preference vote with different setup to not have to include all voteOptions on large scales.

You can select one option. The frontend displays voteOptions as a scale/slider with the increments stored in `voteOptions.voteIncrement` and calculates medians based on votingPower or votes.

```json
{
    "title": "Scale Proposal",
    "ballotId": "ballot._id",
    "description": "A scale vote from 150 to 2500 with increments of 50.",
    "data": {},
    "voteType": "scale",
    "voteIncrement": 50, <-- determines the step size and allowed increments for voteOptions
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": 150, <-- lower bound
            "label": "150 or less",
            "cost": 1
        },
        {
            "id": 2500, <-- upper bound
            "label": "2500 or more",
            "cost": 1
        },
    ],
    "abstainAllowed": true,
}
```

The backend needs to ensure only valid values larger or equal than lower and smaller or equal than upper bound in the set increment are submitted.

This could also look like this, displaying more labels on the frontend:

```json
{
    "title": "Scale Proposal",
    "ballotId": "ballot._id",
    "description": "A scale vote.",
    "data": {},
    "voteType": "scale",
    "voteIncrement": 1,
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": -100, <-- lower bound
            "label": "-100",
            "cost": 1
        },
        {
            "id": 0,
            "label": "Zero",
            "cost": 1
        },
        {
            "id": 100, <-- upper bound
            "label": "100",
            "cost": 1
        },
    ],
    "abstainAllowed": true,
}
```

Leaving in cost for now, maybe we'll find a weird edge case further down the road where this is needed (if the voterBudget has an impact on the ballot for example)
