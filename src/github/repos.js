'use strict';

const { getClient } = require('./client');
const { cached, invalidate } = require('../db/redis/cache');

async function listRepos(telegramUserId, { page = 1, perPage = 5, sort = 'updated' } = {}) {
  const cacheKey = `gitrohub:repos:${telegramUserId}:${sort}:${page}:${perPage}`;
  return cached(cacheKey, 120, async () => {
    const octokit = await getClient(telegramUserId);
    const sortMap = {
      updated: { sort: 'updated', direction: 'desc' },
      created: { sort: 'created', direction: 'desc' },
      name_asc: { sort: 'full_name', direction: 'asc' },
      name_desc: { sort: 'full_name', direction: 'desc' },
    };
    const params = sortMap[sort] || sortMap.updated;
    const { data } = await octokit.rest.repos.listForAuthenticatedUser({
      per_page: perPage,
      page,
      affiliation: 'owner,collaborator,organization_member',
      ...params,
    });
    return data;
  });
}

async function getRepo(telegramUserId, owner, repo) {
  const cacheKey = `gitrohub:repo:${owner}/${repo}`;
  return cached(cacheKey, 120, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.repos.get({ owner, repo });
    return data;
  });
}

async function getLanguages(telegramUserId, owner, repo) {
  const cacheKey = `gitrohub:repo:${owner}/${repo}:languages`;
  return cached(cacheKey, 600, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.repos.listLanguages({ owner, repo });
    return data;
  });
}

async function createRepo(telegramUserId, { name, description, isPrivate, autoInit, gitignoreTemplate, licenseTemplate }) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.createForAuthenticatedUser({
    name,
    description,
    private: isPrivate,
    auto_init: autoInit,
    gitignore_template: gitignoreTemplate || undefined,
    license_template: licenseTemplate || undefined,
  });
  await invalidate(`gitrohub:repos:${telegramUserId}:*`);
  return data;
}

async function deleteRepo(telegramUserId, owner, repo) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.repos.delete({ owner, repo });
  await invalidate(`gitrohub:repos:${telegramUserId}:*`);
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);
}

async function updateRepo(telegramUserId, owner, repo, fields) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.update({ owner, repo, ...fields });
  await invalidate(`gitrohub:repo:${owner}/${repo}*`);
  return data;
}

async function forkRepo(telegramUserId, owner, repo) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.createFork({ owner, repo });
  await invalidate(`gitrohub:repos:${telegramUserId}:*`);
  return data;
}

async function toggleStar(telegramUserId, owner, repo, shouldStar) {
  const octokit = await getClient(telegramUserId);
  if (shouldStar) {
    await octokit.rest.activity.starRepoForAuthenticatedUser({ owner, repo });
  } else {
    await octokit.rest.activity.unstarRepoForAuthenticatedUser({ owner, repo });
  }
}

async function isStarred(telegramUserId, owner, repo) {
  const octokit = await getClient(telegramUserId);
  try {
    await octokit.rest.activity.checkRepoIsStarredByAuthenticatedUser({ owner, repo });
    return true;
  } catch (err) {
    if (err.status === 404) return false;
    throw err;
  }
}

async function toggleWatch(telegramUserId, owner, repo, shouldWatch) {
  const octokit = await getClient(telegramUserId);
  if (shouldWatch) {
    await octokit.rest.activity.setRepoSubscription({ owner, repo, subscribed: true });
  } else {
    await octokit.rest.activity.deleteRepoSubscription({ owner, repo });
  }
}

async function listCollaborators(telegramUserId, owner, repo) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.repos.listCollaborators({ owner, repo });
  return data;
}

async function addCollaborator(telegramUserId, owner, repo, username, permission) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.repos.addCollaborator({ owner, repo, username, permission });
}

async function removeCollaborator(telegramUserId, owner, repo, username) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.repos.removeCollaborator({ owner, repo, username });
}

module.exports = {
  listRepos, getRepo, getLanguages, createRepo, deleteRepo, updateRepo, forkRepo,
  toggleStar, isStarred, toggleWatch, listCollaborators, addCollaborator, removeCollaborator,
};
