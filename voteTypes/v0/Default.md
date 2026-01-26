# Default Vote

The default single option vote with x voteOpions and "abstain" (or not).

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
        }
    ],
    "abstainAllowed": true
}
```

If `abstainAllowed: true` the frontend adds the abstain option and the backend allows `id: "abstain"` as vote submission. This will also allow to run votes where you can either vote or not vote at all. Also: backwards compatible, not that it matters at this point.
