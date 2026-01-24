# VoteType Ranked

A multiselect ranked vote, where you can select as many options as you like until your total budget is equal or below the allowed budget and the order in the vote array determines your preference. Must be possible to not vote all voteOptions.

```json
{
    "title": "Ranked Proposal",
    "ballotId": "ballot._id",
    "description": "A ranked vote, total cost is 3, all items are equally costed at 1.",
    "data": {},
    "voteType": "ranked",
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
    ]
}
```

There also could be a vote where you _must_ rank all available options, which probably needs a new voteType. This also needs an option to abstain from the vote.

On the frontend this probably should randomize the initial voteOptions order to avoid bias.
