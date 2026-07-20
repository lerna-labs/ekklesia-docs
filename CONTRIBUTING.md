# Contributing

Thanks for your interest in improving the Ekklesia documentation.

## Filing issues

This repository is the central issue tracker for the Ekklesia system. Bugs,
feature requests, and questions about the frontend, backend, Hydra integration,
helpers, proposal module, rewards, or the documentation itself all belong here,
filed through
[the issue templates](https://github.com/Lerna-Labs/ekklesia-docs/issues/new/choose).
Every template asks which component is involved so the issue reaches the right
place.

The Hydra SDK is the exception. It is a general purpose library for building on
Cardano Hydra rather than a part of Ekklesia, so it keeps its own tracker. File
SDK issues in [hydra-sdk](https://github.com/lerna-labs/hydra-sdk/issues).

Security vulnerabilities go to neither tracker. See [SECURITY.md](SECURITY.md)
and report privately, never as a public issue in any repository.

## Making a change

1. Branch from `main`. This repository publishes documentation directly, so it
   uses a single branch rather than the promotion model the code repositories
   follow.
2. Make your change.
3. Add a changelog entry if the change warrants one (see below).
4. Run the local checks:
   ```bash
   npm run fmt:check && npm run lint:specs
   ```
   `npm run fmt` will fix formatting for you if the check fails. Changelog
   entries are formatted too, so run this after adding one.
5. Open a pull request into `main`.

Merging to `main` builds and deploys the site to
[docs.ekklesia.vote](https://docs.ekklesia.vote).

## Changelog entries

Every change needs a changelog entry. Add one with:

```bash
npx changeset
```

and follow the prompts. It writes a small markdown file under `.changeset/` that
you commit alongside your change.

The documentation is versioned so it is always clear which release is published,
and the site publishes when a release is cut rather than on every merge. A
change with no entry does not move the release forward, so it would sit merged
but unpublished. That is why editorial work counts too: fixing a typo is a real
change to what a reader sees.

Pick the bump from what the change does:

- `patch` for editorial work: typos, grammar, wording, formatting, broken links
- `minor` for substantive work: a page added, removed, renamed, or moved, an
  OpenAPI spec change, or documented behavior that now reads differently

Write the entry for someone reading the changelog later, not for the reviewer
reading the diff. "Correct the deposit field type in the proposals spec" is
useful. "Fix typo" is not.

Dependency updates and the release pull request are exempt, since neither can
add an entry. Nothing else is.

## Getting set up

See the [README](README.md) for local build instructions.
