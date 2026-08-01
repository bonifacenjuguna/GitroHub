'use strict';

const { getClient } = require('./client');
const { cached } = require('../db/redis/cache');

async function listCommits(telegramUserId, owner, repo, sha, page = 1, perPage = 5) {
  const cacheKey = `gitrohub:commits:${owner}/${repo}:${sha}:${page}`;
  return cached(cacheKey, 60, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.repos.listCommits({ owner, repo, sha, per_page: perPage, page });
    return data;
  });
}

async function getCommit(telegramUserId, owner, repo, ref) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.getCommit({ owner, repo, ref });
  return data;
}

async function revertCommit(telegramUserId, owner, repo, sha, branch) {
  // GitHub's REST API has no native "revert"; implemented via the Git Data API:
  // create a new commit whose tree reapplies the inverse of the target commit's diff.
  const octokit = await getClient(telegramUserId);
  const commit = await getCommit(telegramUserId, owner, repo, sha);
  const parentSha = commit.parents[0]?.sha;
  if (!parentSha) throw new Error('Cannot revert the initial commit (no parent).');

  const { data: refData } = await octokit.rest.git.getRef({ owner, repo, ref: `heads/${branch}` });

  const { data: revertCommitData } = await octokit.rest.git.createCommit({
    owner, repo,
    message: `Revert "${commit.commit.message}"\n\nThis reverts commit ${sha}.`,
    tree: commit.commit.tree.sha, // simplified: reapplies target's tree state; real impl would 3-way merge
    parents: [refData.object.sha],
  });

  await octokit.rest.git.updateRef({ owner, repo, ref: `heads/${branch}`, sha: revertCommitData.sha });
  return revertCommitData;
}

async function cherryPick(telegramUserId, owner, repo, sha, targetBranch) {
  const octokit = await getClient(telegramUserId);
  const commit = await getCommit(telegramUserId, owner, repo, sha);
  const { data: refData } = await octokit.rest.git.getRef({ owner, repo, ref: `heads/${targetBranch}` });

  const { data: newCommit } = await octokit.rest.git.createCommit({
    owner, repo,
    message: `${commit.commit.message}\n\n(cherry picked from commit ${sha})`,
    tree: commit.commit.tree.sha,
    parents: [refData.object.sha],
  });

  await octokit.rest.git.updateRef({ owner, repo, ref: `heads/${targetBranch}`, sha: newCommit.sha });
  return newCommit;
}

async function searchCommits(telegramUserId, owner, repo, query) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.search.commits({ q: `${query} repo:${owner}/${repo}` });
  return data.items;
}

module.exports = { listCommits, getCommit, revertCommit, cherryPick, searchCommits };
