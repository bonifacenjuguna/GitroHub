'use strict';

const { getClient } = require('./client');
const { cached } = require('../db/redis/cache');

async function listWorkflowRuns(telegramUserId, owner, repo) {
  const cacheKey = `gitrohub:actions:${owner}/${repo}`;
  return cached(cacheKey, 30, async () => {
    const octokit = await getClient(telegramUserId);
    const { data } = await octokit.rest.actions.listWorkflowRunsForRepo({ owner, repo, per_page: 10 });
    return data.workflow_runs;
  });
}

async function getRun(telegramUserId, owner, repo, runId) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.actions.getWorkflowRun({ owner, repo, run_id: runId });
  return data;
}

async function listWorkflows(telegramUserId, owner, repo) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.actions.listRepoWorkflows({ owner, repo });
  return data.workflows;
}

async function triggerWorkflow(telegramUserId, owner, repo, workflowId, ref, inputs = {}) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.actions.createWorkflowDispatch({ owner, repo, workflow_id: workflowId, ref, inputs });
}

async function rerunRun(telegramUserId, owner, repo, runId) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.actions.reRunWorkflow({ owner, repo, run_id: runId });
}

async function cancelRun(telegramUserId, owner, repo, runId) {
  const octokit = await getClient(telegramUserId);
  await octokit.rest.actions.cancelWorkflowRun({ owner, repo, run_id: runId });
}

async function getRunLogsUrl(telegramUserId, owner, repo, runId) {
  const octokit = await getClient(telegramUserId);
  // This returns a redirect URL to a downloadable log zip.
  const { url } = await octokit.rest.actions.downloadWorkflowRunLogs({ owner, repo, run_id: runId, request: { redirect: 'manual' } });
  return url;
}

async function listArtifacts(telegramUserId, owner, repo, runId) {
  const octokit = await getClient(telegramUserId);
  const { data } = await octokit.rest.actions.listWorkflowRunArtifacts({ owner, repo, run_id: runId });
  return data.artifacts;
}

async function downloadArtifact(telegramUserId, owner, repo, artifactId) {
  const octokit = await getClient(telegramUserId);
  const response = await octokit.rest.actions.downloadArtifact({ owner, repo, artifact_id: artifactId, archive_format: 'zip' });
  return Buffer.from(response.data);
}

module.exports = {
  listWorkflowRuns, getRun, listWorkflows, triggerWorkflow, rerunRun,
  cancelRun, getRunLogsUrl, listArtifacts, downloadArtifact,
};
