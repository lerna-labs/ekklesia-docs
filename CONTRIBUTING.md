# Contributing

Thanks for your interest in improving the Ekklesia documentation.

## Filing issues

This repository is the central issue tracker for the whole Ekklesia system.
Bugs, feature requests, and questions about the frontend, backend, Hydra
integration, helpers, proposal module, rewards, the SDK, or the documentation
itself all belong here, filed through
[the issue templates](https://github.com/Lerna-Labs/ekklesia-docs/issues/new/choose).
Every template asks which component is involved so the issue reaches the right
place.

Security vulnerabilities are the one exception. See [SECURITY.md](SECURITY.md)
and report privately, never as a public issue in this or any other repository.

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

The documentation is versioned so it is always clear which release is published.
Not every change needs an entry, though. Add one with:

```bash
npx changeset
```

and follow the prompts. It writes a small markdown file under `.changeset/` that
you commit alongside your change.

Add a changelog entry when the change affects what a reader can rely on:

- An OpenAPI spec changes, including a version bump or a corrected field type
- A page is added, removed, renamed, or moved to a different section
- Documented behavior changes, so a reader following the old text would now get
  a different result

Skip the entry for changes that do not alter meaning, such as typo and grammar
fixes, formatting, or link repairs. Apply the `skip-changelog` label to the pull
request so the check passes.

## Getting set up

See the [README](README.md) for local build instructions.
