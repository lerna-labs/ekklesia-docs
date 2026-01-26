# VoteType Ranked

A multiselect ranked vote, where you can select as many options as you like until your total budget is equal or below the allowed budget and the order in the vote array determines your preference. Must be possible to not vote all voteOptions.

```json
{
    "title": "Ranked Proposal with Budget",
    "ballotId": "ballot._id",
    "description": "A ranked vote, total budget is 3, all items have an equal cost of 1",
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
    ],
    "abstainAllowed": true
}
```

Edgecase currently not covered with this: A ranked voted where you _must_ rank all options.

On the frontend this probably should randomize the initial voteOptions order to avoid bias.
