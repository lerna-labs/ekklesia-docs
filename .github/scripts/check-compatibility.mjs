#!/usr/bin/env node
// Check the compatibility table.
//
// compatibility/compatibility.json is the single source of the tested sets.
// This script validates it against the schema, checks that the table on the
// page is exactly what the data renders to, and, given a built site directory,
// checks that the file was published as plain JSON at the expected path.
//
//   node .github/scripts/check-compatibility.mjs [--site _site] [--write]
//
// --write rewrites the table on the page from the data.

import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const DATA = 'compatibility/compatibility.json';
const SCHEMA = 'compatibility/compatibility.schema.json';
const PAGE = 'compatibility/index.md';
const START = '<!-- compatibility-table:start -->';
const END = '<!-- compatibility-table:end -->';

const LABELS = {
  'ekklesia-backend': 'Backend',
  'ekklesia-proposal-module': 'Proposal module',
  'ekklesia-frontend': 'Frontend',
  'ekklesia-hydra': 'Hydra middleware',
};

const args = process.argv.slice(2);
const write = args.includes('--write');
const siteFlag = args.indexOf('--site');
const site = siteFlag === -1 ? null : args[siteFlag + 1];

const failures = [];
const fail = (message) => failures.push(message);

const data = JSON.parse(readFileSync(DATA, 'utf8'));
const schema = JSON.parse(readFileSync(SCHEMA, 'utf8'));

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);
if (!validate(data)) {
  for (const error of validate.errors) {
    fail(`${DATA}${error.instancePath} ${error.message}`);
  }
}

// The published data may not carry a URL (a scheme, "://" or a "www." prefix).
if (/https?:|:\/\/|www\./i.test(JSON.stringify(data))) {
  fail(`${DATA} contains a URL`);
}

// Prettier pads table cells to a common width, so compare without the padding.
const normalize = (text) => text.replace(/-{3,}/g, '---').replace(/\s+/g, ' ').trim();

function render(doc) {
  const lines = [
    '| Tested on | Component | Version | Commit |',
    '| --- | --- | --- | --- |',
  ];
  for (const set of doc.sets) {
    for (const name of Object.keys(LABELS)) {
      const component = set.components?.[name];
      if (!component) continue;
      const commit = component.gitSha ? `\`${component.gitSha.slice(0, 12)}\`` : '';
      lines.push(`| ${set.testedOn} | ${LABELS[name]} | ${component.version} | ${commit} |`);
    }
  }
  for (const set of doc.sets) {
    if (set.notes) lines.push('', `Set tested on ${set.testedOn}: ${set.notes}`);
  }
  return lines.join('\n');
}

if (failures.length === 0) {
  const expected = render(data);
  let page = readFileSync(PAGE, 'utf8');
  const start = page.indexOf(START);
  const end = page.indexOf(END);
  if (start === -1 || end === -1 || end < start) {
    fail(`${PAGE} is missing the table markers`);
  } else {
    const actual = page.slice(start + START.length, end).trim();
    if (normalize(actual) !== normalize(expected)) {
      if (write) {
        page = `${page.slice(0, start + START.length)}\n\n${expected}\n\n${page.slice(end)}`;
        writeFileSync(PAGE, page);
        console.log(`${PAGE} rewritten from ${DATA}`);
      } else {
        fail(`${PAGE} does not match ${DATA}; run with --write to regenerate`);
      }
    }
  }
}

if (site && failures.length === 0) {
  const built = join(site, DATA);
  let served;
  try {
    served = readFileSync(built, 'utf8');
  } catch {
    fail(`${built} was not produced by the build`);
  }
  if (served !== undefined) {
    try {
      const parsed = JSON.parse(served);
      if (JSON.stringify(parsed) !== JSON.stringify(data)) {
        fail(`${built} differs from ${DATA}`);
      }
    } catch {
      fail(`${built} is not valid JSON`);
    }
  }
}

if (failures.length > 0) {
  for (const message of failures) console.error(`FAIL ${message}`);
  process.exit(1);
}
console.log(`compatibility table ok${site ? ` (build output checked in ${site})` : ''}`);
