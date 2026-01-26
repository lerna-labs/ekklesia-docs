# VoteType Preference

A preference vote, where you can select one option.
The frontend displays voteOptions as a scale/slider and calculates medians based on votingPower or votes for the result display.

```json
{
    "title": "Preference Proposal",
    "ballotId": "ballot._id",
    "description": "A preference vote with abstain allowed.",
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
    ],
    "abstainAllowed": true
}
```

A setup could also look like this:

```json
{
    "title": "Preference Proposal",
    "ballotId": "ballot._id",
    "description": "A preference vote with abstain allowed.",
    "data": {},
    "voteType": "preference",
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": -2,
            "label": "Absolutely not",
            "cost": 1
        },
        {
            "id": -1,
            "label": "No",
            "cost": 1
        },
        {
            "id": 0,
            "label": "I don't care",
            "cost": 1
        },
        {
            "id": 1,
            "label": "Yes",
            "cost": 1
        },
        {
            "id": 2,
            "label": "Absolutely!",
            "cost": 1
        }
    ],
    "abstainAllowed": true
}
```

In terms of the median calculation it doesn't make a difference, upper and lower bounds for median calculations are just different.

Leaving in cost for now, maybe we'll find a weird edge case further down the road where this is needed (if the voterBudget has an impact on the ballot for example)

I decided to keep this separate from the scale vote for now, this way you can have dedicated results returned by the API and displayed for each option (which doesn't make sense on the scale vote).
