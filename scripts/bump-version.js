'use strict';

/**
 * Usage: node scripts/bump-version.js <patch|minor|major> "Short description of this release"
 *
 * This is the ONE place version bumps happen. It:
 *   1. Bumps package.json's version (source of truth for /version, /about, etc.)
 *   2. Inserts a dated entry at the top of CHANGELOG.md
 *   3. Prints the exact git commands to commit + tag, so the tag can never
 *      drift out of sync with what's actually in package.json.
 *
 * It does NOT commit or tag automatically — you review the CHANGELOG entry
 * first, then run the printed commands. Keeping a human in the loop here
 * is deliberate: auto-committing a changelog nobody read defeats the point
 * of having one.
 */

const fs = require('fs');
const path = require('path');

const BUMP_TYPE = process.argv[2];
const DESCRIPTION = process.argv.slice(3).join(' ');

const VALID_TYPES = ['patch', 'minor', 'major'];

if (!VALID_TYPES.includes(BUMP_TYPE)) {
  console.error('❌ Usage: node scripts/bump-version.js <patch|minor|major> "Description"');
  console.error('\n   patch — bug fixes, no new features, no breaking changes');
  console.error('   minor — new features, backward-compatible');
  console.error('   major — breaking changes (schema, callback_data scheme, removed features)\n');
  process.exit(1);
}

if (!DESCRIPTION) {
  console.error('❌ A short description is required, e.g.:');
  console.error('   node scripts/bump-version.js patch "Fix ZIP wrapper detection edge case"');
  process.exit(1);
}

const pkgPath = path.join(__dirname, '..', 'package.json');
const changelogPath = path.join(__dirname, '..', 'CHANGELOG.md');

const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
const [major, minor, patch] = pkg.version.split('.').map(Number);

let newVersion;
if (BUMP_TYPE === 'major') newVersion = `${major + 1}.0.0`;
else if (BUMP_TYPE === 'minor') newVersion = `${major}.${minor + 1}.0`;
else newVersion = `${major}.${minor}.${patch + 1}`;

// --- Update package.json ---
pkg.version = newVersion;
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');

// --- Insert CHANGELOG entry ---
const today = new Date().toISOString().slice(0, 10);
const changelog = fs.readFileSync(changelogPath, 'utf8');

const entry = `## [${newVersion}] - ${today}\n\n### ${categoryForType(BUMP_TYPE)}\n- ${DESCRIPTION}\n\n`;

// Insert right after the top "## [Unreleased]" section if present, otherwise
// right after the title/intro block (before the first "## [" entry).
const firstEntryIndex = changelog.indexOf('\n## [');
const updatedChangelog =
  firstEntryIndex === -1
    ? changelog + '\n' + entry
    : changelog.slice(0, firstEntryIndex + 1) + entry + changelog.slice(firstEntryIndex + 1);

fs.writeFileSync(changelogPath, updatedChangelog);

function categoryForType(type) {
  if (type === 'major') return 'Changed';
  if (type === 'minor') return 'Added';
  return 'Fixed';
}

console.log(`\n✅ Bumped version: ${pkg.version === newVersion ? '' : ''}${major}.${minor}.${patch} → ${newVersion}`);
console.log(`✅ CHANGELOG.md updated with a new [${newVersion}] entry\n`);
console.log('Review the CHANGELOG entry, then run:\n');
console.log(`   git add package.json CHANGELOG.md`);
console.log(`   git commit -m "chore: release v${newVersion}"`);
console.log(`   git tag v${newVersion}`);
console.log(`   git push && git push --tags\n`);
console.log('Railway will redeploy on push. The running bot\'s /version command');
console.log('reads package.json directly, so it will reflect the new version and');
console.log('git commit hash automatically once redeployed — no other file needs editing.\n');
