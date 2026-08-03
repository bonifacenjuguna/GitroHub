'use strict';

const AdmZip = require('adm-zip');
const path = require('path');
const { diffAgainstRepo, getGitignorePatterns } = require('./files');
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
 * Runs an async mapper over items with a concurrency cap, instead of
 * either fully sequential (slow) or fully parallel (risks hammering
 * GitHub's API with dozens of simultaneous requests and tripping
 * secondary rate limits). 8 concurrent is a safe, well-tested middle
 * ground for GitHub's API.
 */
async function mapWithConcurrency(items, limit, mapper) {
  const results = new Array(items.length);
  let index = 0;
  async function worker() {
    while (index < items.length) {
      const current = index++;
      results[current] = await mapper(items[current], current);
    }
  }
  const workers = Array.from({ length: Math.min(limit, items.length) }, worker);
  await Promise.all(workers);
  return results;
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
 * unchanged.
 *
 * Diff checks run with capped concurrency (8 at a time) instead of one at
 * a time — for a real-sized project (20-50+ files), the old sequential
 * version meant 20-50 full network round-trips before the user ever saw
 * the comparison screen, which is what made "Strip wrapper" feel stuck.
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

  const classified = await mapWithConcurrency(included, 8, async (file) => {
    const diff = await diffAgainstRepo(telegramUserId, owner, repo, file.fullPath, branch, file.buffer);
    return { file, status: diff.status };
  });

  for (const { file, status } of classified) {
    results[status === 'new' ? 'new' : status === 'modified' ? 'modified' : 'unchanged'].push(file);
  }

  return results;
}

/**
 * Commits a full batch of new+modified files from a ZIP upload as ONE
 * true atomic commit, using the Git Data API directly:
 *   1. Create a blob for each file's content (parallel, capped concurrency)
 *   2. Build a single new tree on top of the branch's current tree,
 *      referencing all the new/updated blobs
 *   3. Create one commit pointing at that tree
 *   4. Move the branch ref to the new commit
 *
 * This replaces the previous approach of N sequential single-file
 * commits via createOrUpdateFileContents, which was both slow (one full
 * network round-trip per file, in sequence) and wrong relative to what
 * we originally designed ("one commit for the whole ZIP push"). A single
 * commit is also what makes this operation safely re-runnable if it ever
 * needs to be retried — partial progress can't be left half-committed
 * across multiple separate commits.
 */
async function commitZipBatch(telegramUserId, owner, repo, branch, filesToCommit, message) {
  if (filesToCommit.length === 0) return [];

  const octokit = await getClient(telegramUserId);

  const { data: refData } = await octokit.rest.git.getRef({ owner, repo, ref: `heads/${branch}` });
  const baseCommitSha = refData.object.sha;

  const { data: baseCommit } = await octokit.rest.git.getCommit({ owner, repo, commit_sha: baseCommitSha });
  const baseTreeSha = baseCommit.tree.sha;

  // Create a blob per file, 8 at a time — parallel instead of sequential,
  // but capped so a huge ZIP doesn't fire 100+ simultaneous requests.
  const blobs = await mapWithConcurrency(filesToCommit, 8, async (file) => {
    const { data } = await octokit.rest.git.createBlob({
      owner, repo,
      content: file.buffer.toString('base64'),
      encoding: 'base64',
    });
    return { path: file.fullPath, sha: data.sha };
  });

  const { data: newTree } = await octokit.rest.git.createTree({
    owner, repo,
    base_tree: baseTreeSha,
    tree: blobs.map((b) => ({ path: b.path, mode: '100644', type: 'blob', sha: b.sha })),
  });

  const { data: newCommit } = await octokit.rest.git.createCommit({
    owner, repo, message,
    tree: newTree.sha,
    parents: [baseCommitSha],
  });

  await octokit.rest.git.updateRef({ owner, repo, ref: `heads/${branch}`, sha: newCommit.sha });

  const { invalidate } = require('../db/redis/cache');
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);

  return { committedPaths: filesToCommit.map((f) => f.fullPath), commitSha: newCommit.sha };
}

module.exports = { extractZip, computeZipDiff, commitZipBatch, matchesGitignore, COMMON_IGNORE_DIRS };
