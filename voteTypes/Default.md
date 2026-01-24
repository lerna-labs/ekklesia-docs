# Default Vote

A single option vote.

```json
{
    "title": "Default Proposal",
    "ballotId": "ballot._id",
    "description": "A default proposal with yes, no, abstain",
    "data": {},
    "voteType": "default",
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": 1,
            "label": "Yes",
            "cost": 1
        },
        {
            "id": 2,
            "label": "No",
            "cost": 1
        },
        {
            "id": 3,
            "label": "Abstain",
            "cost": 1
        },
    ]
}
```

Given we'll need an abstain option on other voteTypes (see [https://github.com/Lerna-Labs/ekklesia-docs/blob/main/voteTypes/Scale.md](Scale.md)), this probably should look like this going forward:

```json
{
    "title": "Default Proposal",
    "ballotId": "ballot._id",
    "description": "A default proposal with yes, no, abstain",
    "data": {},
    "voteType": "default",
    "voterBudget": 1,
    "voteOptions": [
        {
            "id": 1,
            "label": "Yes",
            "cost": 1
        },
        {
            "id": 2,
            "label": "No",
            "cost": 1
        },
    ],
    abstainAllowed: true
}
```

If `abstainAllowed: true` the frontend adds the abstain option and the backend allows `id: "abstain"` as vote submission. This would also allow to run votes where you can either vote or not vote at all. Also: backwards compatible, not that it matters at this point.
