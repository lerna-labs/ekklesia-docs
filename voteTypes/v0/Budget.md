# VoteType Budget

A multiselect vote, where you can select as many options as you like until your total cost of all votes is equal or below the allowed voterBudget.

```json
{
    "title": "Budget Proposal",
    "ballotId": "ballot._id",
    "description": "A budget proposal, total budget is 3, all items costs are 1.",
    "data": {},
    "voteType": "budget",
    "voterBudget": 3,
    "voteOptions": [
        {
            "id": 1,
            "label": "Avocado",
            "cost": 1
        },
        {
            "id": 2,
            "label": "Banana",
            "cost": 1
        },
        {
            "id": 3,
            "label": "Cabbage",
            "cost": 1
        },
        {
            "id": 4,
            "label": "Daikon",
            "cost": 1
        },
        {
            "id": 5,
            "label": "Eggplant",
            "cost": 1
        }
    ],
    "abstainAllowed": true
}
```

This could also look like this, where you could either vote Cabbage or two (or less) other options with no abstain option.

```json
{
    "title": "Budget Proposal",
    "ballotId": "ballot._id",
    "description": "A budget proposal, but items have different costs.",
    "data": {},
    "voteType": "budget",
    "voterBudget": 200,
    "voteOptions": [
        {
            "id": 1,
            "label": "Avocado",
            "cost": 100
        },
        {
            "id": 2,
            "label": "Banana",
            "cost": 100
        },
        {
            "id": 3,
            "label": "Cabbage",
            "cost": 200
        },
        {
            "id": 4,
            "label": "Daikon",
            "cost": 100
        },
        {
            "id": 5,
            "label": "Eggplant",
            "cost": 100
        }
    ],
    "abstainAllowed": false
}
```
