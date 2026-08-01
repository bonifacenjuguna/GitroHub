'use strict';

const { getClient } = require('./client');
const { cached, invalidate } = require('../db/redis/cache');

async function listReleases(telegramUserId, owner, repo) {
  const cacheKey = `gitrohub:releases:${owner}/${repo}`;
  return cached(cacheKey, 120, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.repos.listReleases({ owner, repo, per_page: 10 });
    return data;
  });
}

async function getRelease(telegramUserId, owner, repo, releaseId) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.getRelease({ owner, repo, release_id: releaseId });
  return data;
}

async function generateReleaseNotes(telegramUserId, owner, repo, tagName, previousTag) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.generateReleaseNotes({
    owner, repo, tag_name: tagName, previous_tag_name: previousTag || undefined,
  });
  return data;
}

async function createRelease(telegramUserId, owner, repo, { tagName, targetCommitish, name, body, prerelease }) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.createRelease({
    owner, repo, tag_name: tagName, target_commitish: targetCommitish,
    name, body, prerelease: Boolean(prerelease),
  });
  await invalidate(`gitrohub:releases:${owner}/${repo}`);
  return data;
}

async function deleteRelease(telegramUserId, owner, repo, releaseId) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.repos.deleteRelease({ owner, repo, release_id: releaseId });
  await invalidate(`gitrohub:releases:${owner}/${repo}`);
}

module.exports = { listReleases, getRelease, generateReleaseNotes, createRelease, deleteRelease };
