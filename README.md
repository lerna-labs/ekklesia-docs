# Ekklesia Documentation

Source for [docs.ekklesia.vote](https://docs.ekklesia.vote). Built with Jekyll
and deployed via GitHub Pages.

## Local Development

```bash
bundle install
bundle exec jekyll serve
```

## Formatting

Markdown files are auto-formatted with Prettier (80-char prose wrap, expanded
tables):

```bash
npm install
npm run fmt        # format all markdown
npm run fmt:check  # check without writing
```

## API Integration Tests

The test suite runs against live local API instances and doubles as a QA suite
with comprehensive happy and unhappy path coverage.

### Prerequisites

- **Node.js 22+**
- **Docker** (for local MongoDB and API instances)
- **[cardano-signer](https://github.com/gitmachtl/cardano-signer) >= 1.32.0 on
  PATH**. Used for CIP-30 key generation and message signing.

### Quick Start (Docker)

The test environment runs MongoDB + both APIs + seed data via Docker Compose:

```bash
npm install

# Start everything (MongoDB, Voting API, Proposals API, seed data)
npm run env:up

# Copy the pre-configured Docker env
cp __tests/.env.docker __tests/.env

# Run all tests
npm test

# When done
npm run env:down
```

### Environment Commands

```bash
npm run env:up       # start MongoDB + APIs + seed data
npm run env:down     # stop everything (keeps data)
npm run env:reset    # stop, wipe data, restart fresh
npm run env:logs     # tail all container logs
```

> **Note:** The rate limit tests intentionally exhaust API rate limits. If you
> need to re-run the test suite, reset the environment first with
> `npm run env:reset` or wait ~60 seconds for the rate limit windows to expire.

### Running Tests

```bash
npm test                  # all tests
npm run test:voting       # voting API only
npm run test:proposals    # proposals API only
```

Test keys (DRep, Pool) are **auto-generated** via `cardano-signer` on first run
and cached in `__tests/keys/`. No manual key setup needed.

### Manual Setup (without Docker)

If you prefer to run the APIs natively, see `__tests/.env.example` for the
required environment variables and configure accordingly.

## Adding Downloads

Downloads are managed as a Jekyll collection. To add a new downloadable
resource:

1. Create a file in `_downloads/` with the following frontmatter:

```yaml
---
title: "Ekklesia API — Postman Collection"
description: "Pre-built Postman collection for the Backend API"
version: "v0.1.0"
size: "12 KB"
file: "/downloads/_files/ekklesia-api.postman_collection.json"
---
```

2. Place the actual file in `downloads/_files/`.

The download will automatically appear on the Downloads page.
