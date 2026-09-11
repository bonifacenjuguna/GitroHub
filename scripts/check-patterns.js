#!/usr/bin/env node
/**
 * check-patterns.js — permanent home for the two bug-class detectors that
 * were originally written as one-off audit scripts, run by hand, and
 * thrown away afterward. That meant every check only ever caught bugs
 * that already existed at the moment someone happened to remember to run
 * it — this file exists so the same checks run automatically, every
 * time, via `npm run check:patterns` (or `npm run verify`).
 *
 * Exits non-zero (failing CI / a pre-deploy check) if EXIT_ON_FINDINGS is
 * true for a given check and it finds something. Two checks are strict
 * (zero tolerance, exit non-zero on any hit) because they've never
 * produced a false positive in practice. The third is informational only
 * — it has a real false-positive rate (JS code inside template
 * interpolations, SQL, plain-text replies with no MarkdownV2 parse_mode
 * all look superficially similar to real hits) so it prints candidates
 * for a human to glance at instead of failing the build over noise.
 *
 * CHECK 1 — require-scope bugs ("the ephemeral bug"): a `const X =
 * require(...)` declared inside one function, then referenced (X.foo() /
 * X()) inside a DIFFERENT function in the same file that has no require
 * of its own for X and isn't covered by a module-level import either.
 * This is what caused several real ReferenceError crashes across this
 * codebase — ESLint's no-undef (see .eslintrc.json) also catches this at
 * lint time, but this check stays as a second, independent net.
 *
 * CHECK 2 — doubled-backslash Unicode escapes: `\\uXXXX` where `\uXXXX`
 * was clearly intended (e.g. `won\\u2019t` instead of `won\u2019t`).
 * Produces garbled visible text, not a crash, but has zero known false
 * positives, so it's strict too.
 *
 * CHECK 3 — unescaped MarkdownV2 reserved characters in message text.
 * Informational only, see above.
 */

const fs = require('fs');
const path = require('path');

const SRC_DIR = path.join(__dirname, '..', 'src');

function listJsFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listJsFiles(full));
    else if (entry.name.endsWith('.js')) out.push(full);
  }
  return out;
}

const files = listJsFiles(SRC_DIR);
let hadStrictFindings = false;

// ─── CHECK 1: require-scope bugs ────────────────────────────────────
function findFunctionRanges(lines) {
  const ranges = [];
  let i = 0;
  while (i < lines.length) {
    const m = lines[i].match(/^(async\s+)?function\s+(\w+)\s*\(/);
    if (m) {
      const name = m[2];
      let depth = 0;
      let started = false;
      let j = i;
      while (j < lines.length) {
        depth += (lines[j].match(/\{/g) || []).length - (lines[j].match(/\}/g) || []).length;
        if (lines[j].includes('{')) started = true;
        if (started && depth <= 0) break;
        j++;
      }
      ranges.push({ start: i, end: j, name });
      i = j + 1;
    } else {
      i++;
    }
  }
  return ranges;
}

function extractRequireNames(line) {
  const names = [];
  const destructure = line.match(/^\s*const\s*\{([^}]*)\}\s*=\s*require\(/);
  if (destructure) {
    for (const part of destructure[1].split(',')) {
      names.push(part.trim().split(':')[0].trim());
    }
    return names;
  }
  const single = line.match(/^\s*const\s+(\w+)\s*=\s*require\(/);
  if (single) names.push(single[1]);
  return names;
}

console.log('── Checking for require-scope bugs (the "ephemeral" bug class) ──');
let requireScopeFindings = 0;
for (const file of files) {
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  const ranges = findFunctionRanges(lines);

  const moduleLevelVars = new Set();
  for (let i = 0; i < lines.length; i++) {
    if (ranges.some((r) => r.start <= i && i <= r.end)) continue;
    if (/^const\s/.test(lines[i])) extractRequireNames(lines[i]).forEach((n) => moduleLevelVars.add(n));
  }

  const funcLocalRequires = {};
  for (const r of ranges) {
    const local = new Set();
    for (let k = r.start; k <= r.end; k++) {
      extractRequireNames(lines[k]).forEach((n) => local.add(n));
    }
    funcLocalRequires[r.name] = local;
  }

  const allRequired = new Set(moduleLevelVars);
  for (const set of Object.values(funcLocalRequires)) for (const n of set) allRequired.add(n);

  const identRe = /\b([a-zA-Z_]\w*)\s*[.(]/g;
  for (const r of ranges) {
    const used = new Set();
    for (let k = r.start; k <= r.end; k++) {
      let m;
      identRe.lastIndex = 0;
      while ((m = identRe.exec(lines[k]))) used.add(m[1]);
    }
    for (const name of used) {
      const isRequiredSomewhereElse = allRequired.has(name);
      const isAvailableHere = moduleLevelVars.has(name) || funcLocalRequires[r.name].has(name);
      if (isRequiredSomewhereElse && !isAvailableHere) {
        console.log(`  ✗ ${path.relative(process.cwd(), file)}: '${name}' used in ${r.name}() but only required in a different function`);
        requireScopeFindings++;
      }
    }
  }
}
if (requireScopeFindings === 0) {
  console.log('  ✓ clean');
} else {
  hadStrictFindings = true;
}

// ─── CHECK 2: doubled-backslash Unicode escapes ─────────────────────
console.log('\n── Checking for doubled-backslash Unicode escapes (e.g. \\\\u2019) ──');
let unicodeFindings = 0;
for (const file of files) {
  const content = fs.readFileSync(file, 'utf8');
  const re = /\\\\u[0-9a-fA-F]{4}/g;
  let m;
  while ((m = re.exec(content))) {
    const lineNo = content.slice(0, m.index).split('\n').length;
    console.log(`  ✗ ${path.relative(process.cwd(), file)}:${lineNo}: found '${m[0]}' — almost certainly meant to be a single-backslash escape`);
    unicodeFindings++;
  }
}
if (unicodeFindings === 0) {
  console.log('  ✓ clean');
} else {
  hadStrictFindings = true;
}

// ─── CHECK 3: unescaped MarkdownV2 reserved characters (informational) ──
console.log('\n── Scanning for possibly-unescaped MarkdownV2 characters (informational — review, don\u2019t assume) ──');
const mdFiles = files.filter((f) => fs.readFileSync(f, 'utf8').includes('MarkdownV2'));
let mdCandidates = 0;
const tmplRe = /`([^`]*)`/gs;
const interpRe = /\$\{[^}]*\}/g;
for (const file of mdFiles) {
  const content = fs.readFileSync(file, 'utf8');
  let m;
  tmplRe.lastIndex = 0;
  while ((m = tmplRe.exec(content))) {
    const stripped = m[1].replace(interpRe, '');
    // Only raw parens are flagged — the one reserved char that's actually
    // shown up as a real bug, and prose is much more likely to contain a
    // stray "(" than the other reserved characters, which mostly appear
    // as intentional Markdown syntax (*bold*, already-escaped \\-, etc).
    if (/(?<!\\)[()]/.test(stripped) && stripped.trim().length > 0 && !stripped.includes('=>') && !stripped.includes('function')) {
      const lineNo = content.slice(0, m.index).split('\n').length;
      console.log(`  ? ${path.relative(process.cwd(), file)}:${lineNo}: template literal has a raw ( or ) — verify it's escaped as \\\\( \\\\) if this text uses parse_mode MarkdownV2`);
      mdCandidates++;
    }
  }
}
console.log(mdCandidates === 0 ? '  ✓ no candidates found' : `  (${mdCandidates} candidate(s) above — most are false positives from JS code inside template interpolations; only act on ones that are clearly plain prose)`);

console.log('');
if (hadStrictFindings) {
  console.log('❌ check-patterns found issues that need fixing before this ships.');
  process.exit(1);
}
console.log('✅ check-patterns: no strict findings.');
