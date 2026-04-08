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
