'use strict';

const AdmZip = require('adm-zip');
const path = require('path');
const { diffAgainstRepo, getGitignorePatterns, commitFile } = require('./files');
const { getClient } = require('./client');

const JUNK_PATTERNS = [/^__MACOSX\//, /\.DS_Store$/, /^Thumbs\.db$/, /^\.git\//];
const COMMON_IGNORE_DIRS = ['node_modules/', 'dist/', 'build/', '.env', '__pycache__/', 'vendor/', 'target/'];

function isJunk(entryName) {
  return JUNK_PATTERNS.some((re) => re.test(entryName));
}

/** Very small glob-ish matcher good enough for typical .gitignore patterns (dirs, extensions, exact names). */
function matchesGitignore(entryPath, patterns) {
  return patterns.some((pattern) => {
    const clean = pattern.replace(/^\//, '').replace(/\/$/, '');
    if (pattern.endsWith('/')) return entryPath.startsWith(clean + '/') || entryPath === clean;
    if (pattern.includes('*')) {
      const re = new RegExp('^' + clean.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$');
      return re.test(entryPath) || re.test(path.basename(entryPath));
    }
    return entryPath === clean || entryPath.startsWith(clean + '/') || path.basename(entryPath) === clean;
  });
}

/**
 * Extracts a ZIP buffer into a flat list of { path, buffer } entries,
 * detecting and stripping a single wrapper folder (e.g. "my-project-main/")
 * after filtering out known junk (__MACOSX, .DS_Store, .git/).
 */
function extractZip(zipBuffer) {
  const zip = new AdmZip(zipBuffer);
  const entries = zip.getEntries().filter((e) => !e.isDirectory && !isJunk(e.entryName));

  const topLevelSegments = new Set(entries.map((e) => e.entryName.split('/')[0]));
  let wrapper = null;
  if (topLevelSegments.size === 1) {
    const only = [...topLevelSegments][0];
    const allNested = entries.every((e) => e.entryName.startsWith(only + '/'));
    if (allNested) wrapper = only;
  }

  const files = entries.map((e) => ({
    path: wrapper ? e.entryName.slice(wrapper.length + 1) : e.entryName,
    buffer: e.getData(),
  }));

  return { wrapperDetected: wrapper, files };
}

/**
 * Compares extracted ZIP files against the target repo/branch/folder scope,
 * applying .gitignore rules, and classifies each file as new / modified /
 * unchanged. Also computes which existing repo files (within scope) are
 * missing from the ZIP.
 */
async function computeZipDiff(telegramUserId, owner, repo, branch, targetFolder, files, { applyGitignore = true } = {}) {
  const patterns = applyGitignore ? await getGitignorePatterns(telegramUserId, owner, repo, branch) : [];

  const scoped = files.map((f) => ({
    ...f,
    fullPath: targetFolder ? `${targetFolder.replace(/\/$/, '')}/${f.path}` : f.path,
  }));

  const excluded = scoped.filter((f) => matchesGitignore(f.fullPath, patterns));
  const included = scoped.filter((f) => !matchesGitignore(f.fullPath, patterns));

  const results = { new: [], modified: [], unchanged: [], excludedCount: excluded.length };

  for (const file of included) {
    const diff = await diffAgainstRepo(telegramUserId, owner, repo, file.fullPath, branch, file.buffer);
    results[diff.status === 'new' ? 'new' : diff.status === 'modified' ? 'modified' : 'unchanged'].push(file);
  }

  return results;
}

/** Commits a full batch of new+modified files from a ZIP upload as one logical push (sequential commits, single message pattern). */
async function commitZipBatch(telegramUserId, owner, repo, branch, filesToCommit, message) {
  const committed = [];
  for (const file of filesToCommit) {
    await commitFile(telegramUserId, owner, repo, {
      path: file.fullPath,
      branch,
      content: file.buffer,
      message,
    });
    committed.push(file.fullPath);
  }
  return committed;
}

module.exports = { extractZip, computeZipDiff, commitZipBatch, matchesGitignore, COMMON_IGNORE_DIRS };
