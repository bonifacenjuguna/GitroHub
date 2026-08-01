'use strict';

const crypto = require('crypto');
const { getClient } = require('./client');
const { invalidate } = require('../db/redis/cache');

/** Lists the contents of a folder (or root) at a given path/branch. */
async function listFolder(telegramUserId, owner, repo, path = '', branch) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.getContent({ owner, repo, path, ref: branch });
  const items = Array.isArray(data) ? data : [data];
  return items
    .sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'dir' ? -1 : 1));
}

/** Fetches a single file's content + sha (sha is required for update/delete calls). */
async function getFile(telegramUserId, owner, repo, path, branch) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.getContent({ owner, repo, path, ref: branch });
  if (Array.isArray(data)) throw new Error(`${path} is a directory, not a file`);
  return {
    ...data,
    content: data.encoding === 'base64' ? Buffer.from(data.content, 'base64').toString('utf8') : data.content,
  };
}

/** Returns null if the file does not exist at this path (used for the exists-check before upload). */
async function tryGetFile(telegramUserId, owner, repo, path, branch) {
  try {
    return await getFile(telegramUserId, owner, repo, path, branch);
  } catch (err) {
    if (err.status === 404) return null;
    throw err;
  }
}

function sha1Hex(buffer) {
  return crypto.createHash('sha1').update(buffer).digest('hex');
}

/**
 * Core diff-detection logic used by every upload flow (single file, ZIP,
 * "Upload Here" shortcut). Compares new content against what's currently
 * at that path and returns a classification, never committing anything
 * itself — commit is a separate, explicit step the user confirms.
 */
async function diffAgainstRepo(telegramUserId, owner, repo, path, branch, newContentBuffer) {
  const existing = await tryGetFile(telegramUserId, owner, repo, path, branch);
  if (!existing) {
    return { status: 'new', existing: null };
  }
  const existingBuffer = Buffer.from(existing.content, 'utf8');
  const identical = sha1Hex(existingBuffer) === sha1Hex(newContentBuffer)
    || Buffer.compare(existingBuffer, newContentBuffer) === 0;
  if (identical) {
    return { status: 'unchanged', existing };
  }
  return { status: 'modified', existing };
}

/** Creates or updates a single file with a commit message. Handles both new + modified paths. */
async function commitFile(telegramUserId, owner, repo, { path, branch, content, message, existingSha }) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.createOrUpdateFileContents({
    owner, repo, path, branch, message,
    content: Buffer.isBuffer(content) ? content.toString('base64') : Buffer.from(content, 'utf8').toString('base64'),
    sha: existingSha || undefined,
  });
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);
  return data;
}

async function deleteFile(telegramUserId, owner, repo, { path, branch, message, sha }) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.deleteFile({ owner, repo, path, branch, message, sha });
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);
  return data;
}

/**
 * Renames or moves a file. GitHub's contents API has no native rename, so
 * this is implemented as: read old file -> create new path -> delete old path,
 * batched via the Git Trees API as a single commit rather than two separate
 * commits, so history stays clean.
 */
async function moveFile(telegramUserId, owner, repo, { oldPath, newPath, branch, message }) {
  const octokit = await getClient(telegramUserId);

  const { data: refData } = await octokit.rest.git.getRef({ owner, repo, ref: `heads/${branch}` });
  const latestCommitSha = refData.object.sha;

  const { data: commitData } = await octokit.rest.git.getCommit({ owner, repo, commit_sha: latestCommitSha });
  const baseTreeSha = commitData.tree.sha;

  const oldFile = await getFile(telegramUserId, owner, repo, oldPath, branch);

  const { data: newTree } = await octokit.rest.git.createTree({
    owner, repo, base_tree: baseTreeSha,
    tree: [
      { path: oldPath, mode: '100644', type: 'blob', sha: null }, // remove old path
      { path: newPath, mode: '100644', type: 'blob', content: oldFile.content }, // add new path
    ],
  });

  const { data: newCommit } = await octokit.rest.git.createCommit({
    owner, repo, message, tree: newTree.sha, parents: [latestCommitSha],
  });

  await octokit.rest.git.updateRef({ owner, repo, ref: `heads/${branch}`, sha: newCommit.sha });
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);
  return newCommit;
}

/** Fetches and parses a repo's .gitignore into an array of glob patterns (comments/blank lines stripped). */
async function getGitignorePatterns(telegramUserId, owner, repo, branch) {
  const file = await tryGetFile(telegramUserId, owner, repo, '.gitignore', branch);
  if (!file) return [];
  return file.content
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'));
}

/** Downloads a repo (or branch) as a ZIP buffer via GitHub's zipball endpoint. */
async function downloadZipball(telegramUserId, owner, repo, ref) {
  const octokit = await getClient(telegramUserId);
  const response = await octokit.rest.repos.downloadZipballArchive({ owner, repo, ref });
  return Buffer.from(response.data);
}

/** Searches code within a single repo. */
async function searchCodeInRepo(telegramUserId, owner, repo, term) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.search.code({ q: `${term} repo:${owner}/${repo}` });
  return data.items;
}

/** Global code search across all of the user's accessible repos. */
async function searchCodeGlobal(telegramUserId, term, { language, repo } = {}) {
  const octokit = await getClient(telegramUserId);
  let q = term;
  if (language) q += ` language:${language}`;
  if (repo) q += ` repo:${repo}`;
  const { data } = await octokit.rest.search.code({ q });
  return data.items;
}

module.exports = {
  listFolder, getFile, tryGetFile, diffAgainstRepo, commitFile, deleteFile,
  moveFile, getGitignorePatterns, downloadZipball, searchCodeInRepo, searchCodeGlobal,
};
