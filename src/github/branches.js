'use strict';

const { getClient } = require('./client');
const { cached, invalidate } = require('../db/redis/cache');

async function listBranches(telegramUserId, owner, repo) {
  const cacheKey = `gitrohub:branches:${owner}/${repo}`;
  return cached(cacheKey, 90, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.repos.listBranches({ owner, repo, per_page: 100 });
    return data;
  });
}

async function getBranch(telegramUserId, owner, repo, branch) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.getBranch({ owner, repo, branch });
  return data;
}

async function compareBranches(telegramUserId, owner, repo, base, head) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.compareCommits({ owner, repo, base, head });
  return data;
}

async function createBranch(telegramUserId, owner, repo, newBranchName, fromBranch) {
  const octokit = await getClient(telegramUserId);
  const { data: ref } = await octokit.rest.git.getRef({ owner, repo, ref: `heads/${fromBranch}` });
  const { data } = await octokit.rest.git.createRef({
    owner, repo,
    ref: `refs/heads/${newBranchName}`,
    sha: ref.object.sha,
  });
  await invalidate(`gitrohub:branches:${owner}/${repo}`);
  return data;
}

async function deleteBranch(telegramUserId, owner, repo, branch) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.git.deleteRef({ owner, repo, ref: `heads/${branch}` });
  await invalidate(`gitrohub:branches:${owner}/${repo}`);
}

async function renameBranch(telegramUserId, owner, repo, branch, newName) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.renameBranch({ owner, repo, branch, new_name: newName });
  await invalidate(`gitrohub:branches:${owner}/${repo}`);
  return data;
}

async function setDefaultBranch(telegramUserId, owner, repo, branch) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.repos.update({ owner, repo, default_branch: branch });
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);
}

/** Deletes every branch already merged into the default branch. Returns list of deleted names. */
async function deleteMergedBranches(telegramUserId, owner, repo, defaultBranch) {
  const branches = await listBranches(telegramUserId, owner, repo);
  const deleted = [];
  for (const b of branches) {
    if (b.name === defaultBranch) continue;
    const comparison = await compareBranches(telegramUserId, owner, repo, defaultBranch, b.name);
    if (comparison.status === 'identical' || comparison.status === 'behind') {
      await deleteBranch(telegramUserId, owner, repo, b.name);
      deleted.push(b.name);
    }
  }
  return deleted;
}

module.exports = {
  listBranches, getBranch, compareBranches, createBranch,
  deleteBranch, renameBranch, setDefaultBranch, deleteMergedBranches,
};
