'use strict';

const { getClient } = require('./client');
const { cached, invalidate } = require('../db/redis/cache');

async function listIssues(telegramUserId, owner, repo, state = 'open') {
  const cacheKey = `gitrohub:issues:${owner}/${repo}:${state}`;
  return cached(cacheKey, 60, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.issues.listForRepo({ owner, repo, state, per_page: 20 });
    return data.filter((i) => !i.pull_request); // exclude PRs, GitHub's API mixes them in
  });
}

async function getIssue(telegramUserId, owner, repo, issueNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.get({ owner, repo, issue_number: issueNumber });
  return data;
}

async function createIssue(telegramUserId, owner, repo, { title, body, labels }) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.create({ owner, repo, title, body, labels });
  await invalidate(`gitrohub:issues:${owner}/${repo}:*`);
  return data;
}

async function closeIssue(telegramUserId, owner, repo, issueNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.update({ owner, repo, issue_number: issueNumber, state: 'closed' });
  await invalidate(`gitrohub:issues:${owner}/${repo}:*`);
  return data;
}

async function reopenIssue(telegramUserId, owner, repo, issueNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.update({ owner, repo, issue_number: issueNumber, state: 'open' });
  await invalidate(`gitrohub:issues:${owner}/${repo}:*`);
  return data;
}

async function addComment(telegramUserId, owner, repo, issueNumber, body) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.createComment({ owner, repo, issue_number: issueNumber, body });
  return data;
}

async function setLabels(telegramUserId, owner, repo, issueNumber, labels) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.setLabels({ owner, repo, issue_number: issueNumber, labels });
  return data;
}

async function assignUsers(telegramUserId, owner, repo, issueNumber, assignees) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.addAssignees({ owner, repo, issue_number: issueNumber, assignees });
  return data;
}

async function listMilestones(telegramUserId, owner, repo) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.listMilestones({ owner, repo, state: 'open' });
  return data;
}

async function createMilestone(telegramUserId, owner, repo, title, dueOn) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.createMilestone({ owner, repo, title, due_on: dueOn || undefined });
  return data;
}

async function setMilestone(telegramUserId, owner, repo, issueNumber, milestoneNumber) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.issues.update({ owner, repo, issue_number: issueNumber, milestone: milestoneNumber });
  return data;
}

module.exports = {
  listIssues, getIssue, createIssue, closeIssue, reopenIssue, addComment,
  setLabels, assignUsers, listMilestones, createMilestone, setMilestone,
};
