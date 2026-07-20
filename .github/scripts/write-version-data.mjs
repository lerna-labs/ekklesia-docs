#!/usr/bin/env node
// Write the site version and build date where Jekyll can read them.
//
// Jekyll has no way to read package.json, so the build writes the values it
// needs into _data/version.yml first. The file is generated, not committed,
// which keeps the published version tied to the build rather than to whoever
// last remembered to update a string by hand.

import { mkdirSync, writeFileSync } from 'node:fs';
import { readFileSync } from 'node:fs';

const { version } = JSON.parse(readFileSync('package.json', 'utf8'));
const built = new Date().toISOString().slice(0, 10);

mkdirSync('_data', { recursive: true });
writeFileSync('_data/version.yml', `version: '${version}'\nbuilt: '${built}'\n`);

console.log(`_data/version.yml written: v${version}, built ${built}`);
