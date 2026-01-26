# VoteType Preference

A preference vote, where you can select one option.
The frontend displays voteOptions as a scale/slider and calculates medians based on votingPower or votes.

```json
{
    "title": "Preference Proposal",
    "ballotId": "ballot._id",
    "description": "A preference vote.",
    "data": {},
    "voteType": "preference",
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": 1,
            "label": "Absolutely not",
            "cost": 1
        },
        {
            "id": 2,
            "label": "No",
            "cost": 1
        },
        {
            "id": 3,
            "label": "I don't care",
            "cost": 1
        },
        {
            "id": 4,
            "label": "Yes",
            "cost": 1
        },
        {
            "id": 5,
            "label": "Absolutely!",
            "cost": 1
        }
    ]
}
```

A setup could also look like this:

```json
{
    "title": "Preference Proposal",
    "ballotId": "ballot._id",
    "description": "A preference vote.",
    "data": {},
    "voteType": "preference",
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": 1,
            "label": "Absolutely not",
            "cost": -2
        },
        {
            "id": 2,
            "label": "No",
            "cost": 1
        },
        {
            "id": 3,
            "label": "I don't care",
            "cost": 0
        },
        {
            "id": 4,
            "label": "Yes",
            "cost": 1
        },
        {
            "id": 5,
            "label": "Absolutely!",
            "cost": 2
        }
    ]
}
```

In terms of the median calculation it doesn't make a difference, upper and lower bounds for median calculations are just different.

Needs an option to abstain from the vote, see [https://github.com/Lerna-Labs/ekklesia-docs/blob/main/voteTypes/Scale.md](Scale.md)
