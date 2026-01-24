# VoteType Scale

Basically a preference vote with different setup to not have to include all voteOptions on large scales.

You can select one option. The frontend displays voteOptions as a scale/slider with the increments stored in `voteOptions[0].cost` and calculates medians based on votingPower or votes.

Setup could be:

```json
{
    "title": "Scale Proposal",
    "ballotId": "ballot._id",
    "description": "A scale vote.",
    "data": {},
    "voteType": "scale",
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
    ]
}
```

The backend needs to ensure only valid values larger or equal than lower and smaller or equal than upper bound in the set increment are submitted.

This could also look like this:

```json
{
    "title": "Scale Proposal",
    "ballotId": "ballot._id",
    "description": "A scale vote.",
    "data": {},
    "voteType": "scale",
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": -100, <-- lower bound
            "label": "-100",
            "cost": 5
        },
        {
            "id": 0,
            "label": "Zero",
            "cost": 5
        },
        {
            "id": 100, <-- upper bound
            "label": "100",
            "cost": 5
        },
    ]
}
```

Needs an option to completely abstain from the vote, but the abstain value can't be 0 as 0 might very well be a valid voteOption.

This could work:

```json
        {
            "id": "abstain",
            "label": "Abstain",
            "cost": 0
        }
```

