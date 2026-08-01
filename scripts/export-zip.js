'use strict';

/**
 * Usage: node scripts/export-zip.js
 *
 * Packages the project into dist/gitrohub-v<version>.zip, where <version>
 * is read directly from package.json — never hardcoded, so the zip
 * filename can never drift out of sync with the code inside it the way a
 * manually-named zip could after a version bump.
 *
 * Run this AFTER npm run release:patch/minor/major (and after committing/
 * tagging), not instead of it — this script only produces a distributable
 * archive, it doesn't touch version numbers itself.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));

const distDir = path.join(ROOT, 'dist');
if (!fs.existsSync(distDir)) fs.mkdirSync(distDir);

const zipName = `gitrohub-v${pkg.version}.zip`;
const zipPath = path.join(distDir, zipName);

if (fs.existsSync(zipPath)) {
  fs.unlinkSync(zipPath); // overwrite if re-exporting the same version
}

// Exclude node_modules, git internals, .env (never ship real secrets),
// and any previous dist/ output from being zipped into itself.
const EXCLUDES = ['node_modules/*', '.git/*', '.env', 'dist/*'];
const excludeArgs = EXCLUDES.map((p) => `-x "${p}"`).join(' ');

try {
  execSync(`cd "${ROOT}/.." && zip -r -q "${zipPath}" "${path.basename(ROOT)}" ${excludeArgs}`, {
    stdio: 'inherit',
  });
  console.log(`\n✅ Exported: dist/${zipName}\n`);
} catch (err) {
  console.error('❌ Export failed — is `zip` installed on this machine?');
  process.exit(1);
}
