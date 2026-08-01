'use strict';

const { getClient } = require('./client');
const { cached, invalidate } = require('../db/redis/cache');

async function listPulls(telegramUserId, owner, repo, state = 'open') {
  const cacheKey = `gitrohub:prs:${owner}/${repo}:${state}`;
  return cached(cacheKey, 60, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.pulls.list({ owner, repo, state, per_page: 20 });
    return data;
  });
}

async function getPull(telegramUserId, owner, repo, pullNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.pulls.get({ owner, repo, pull_number: pullNumber });
  return data;
}

async function createPull(telegramUserId, owner, repo, { title, body, head, base, draft }) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.pulls.create({ owner, repo, title, body, head, base, draft: Boolean(draft) });
  await invalidate(`gitrohub:prs:${owner}/${repo}:*`);
  return data;
}

async function mergePull(telegramUserId, owner, repo, pullNumber, mergeMethod = 'merge') {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.pulls.merge({ owner, repo, pull_number: pullNumber, merge_method: mergeMethod });
  await invalidate(`gitrohub:prs:${owner}/${repo}:*`);
  return data;
}

async function closePull(telegramUserId, owner, repo, pullNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.pulls.update({ owner, repo, pull_number: pullNumber, state: 'closed' });
  await invalidate(`gitrohub:prs:${owner}/${repo}:*`);
  return data;
}

async function requestReviewers(telegramUserId, owner, repo, pullNumber, reviewers) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.pulls.requestReviewers({ owner, repo, pull_number: pullNumber, reviewers });
  return data;
}

async function getDiff(telegramUserId, owner, repo, pullNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.pulls.get({
    owner, repo, pull_number: pullNumber,
    mediaType: { format: 'diff' },
  });
  return data;
}

async function getTemplate(telegramUserId, owner, repo, branch) {
  const { tryGetFile } = require('./files');
  return tryGetFile(telegramUserId, owner, repo, '.github/PULL_REQUEST_TEMPLATE.md', branch);
}

module.exports = { listPulls, getPull, createPull, mergePull, closePull, requestReviewers, getDiff, getTemplate };
