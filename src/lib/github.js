const { Octokit } = require('@octokit/rest');

/**
 * Thin wrapper around Octokit implementing every GitHub operation GitroHub's
 * menus map to. One function per bot action, so handlers stay declarative
 * and error-shaping (per our "specific errors always" rule) happens in
 * exactly one place per operation.
 *
 * Clients are cached per token instead of constructed fresh on every call —
 * building a new Octokit instance isn't free (route methods, request
 * wrappers, hooks all get rebuilt), and doing it on every single API call
 * was adding real allocation churn under load. Capped at 3 entries as a
 * defensive bound (a single-owner bot only ever really has one token, but
 * this avoids unbounded growth across reconnects with different tokens).
 */
const clientCache = new Map();
function client(token) {
  if (clientCache.has(token)) return clientCache.get(token);
  const octo = new Octokit({ auth: token });
  clientCache.set(token, octo);
  if (clientCache.size > 3) {
    clientCache.delete(clientCache.keys().next().value);
  }
  return octo;
}

/**
 * True if the error looks like a genuine rate-limit rejection (403 with
 * the specific rate-limit headers/message GitHub uses), as opposed to a
 * permissions 403 — those need very different messages.
 */
function isRateLimitError(err) {
  return !!(err && err.status === 403 && /rate limit/i.test(err.message || ''));
}

/**
 * Retries ONE time, with a short delay, for transient failures only —
 * network blips and 5xx server errors. Deliberately only used on
 * idempotent READ operations below; wrapping writes (create/delete/put)
 * would risk double-executing a mutation if the first attempt actually
 * succeeded but the response was lost in transit.
 */
/**
 * Retries ONE time, with a short delay, for transient failures only —
 * network blips and 5xx server errors. Deliberately only used on
 * idempotent READ operations below; wrapping writes (create/delete/put)
 * would risk double-executing a mutation if the first attempt actually
 * succeeded but the response was lost in transit.
 *
 * Also races every call against a hard timeout. This matters more than it
 * might look: incoming Telegram updates are now processed one at a time
 * (see bot.js), so a single GitHub call that hangs indefinitely would
 * block every subsequent interaction — including /start — behind it.
 * Bounding every call here is what makes that serialization safe.
 */
const REQUEST_TIMEOUT_MS = 15000;

function withTimeout(promise, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${REQUEST_TIMEOUT_MS}ms`)), REQUEST_TIMEOUT_MS)),
  ]);
}

async function withRetry(fn) {
  try {
    return await withTimeout(fn(), 'GitHub API request');
  } catch (err) {
    const transient = (err.status >= 500 && err.status < 600) || !err.status;
    if (!transient || isRateLimitError(err)) throw err; // rate limits shouldn't be retried immediately
    await new Promise((resolve) => setTimeout(resolve, 600));
    return withTimeout(fn(), 'GitHub API request (retry)');
  }
}

async function getAuthenticatedUser(token) {
  return withRetry(async () => {
    const octo = client(token);
    const { data } = await octo.users.getAuthenticated();
    return data; // { login, avatar_url, ... }
  });
}

async function getRateLimit(token) {
  return withRetry(async () => {
    const octo = client(token);
    const { data } = await octo.rateLimit.get();
    return data.resources.core; // { limit, remaining, reset }
  });
}

async function listRepos(token, { sort = 'updated', direction = 'desc' } = {}) {
  return withRetry(async () => {
    const octo = client(token);
    return octo.paginate(octo.repos.listForAuthenticatedUser, {
      per_page: 100,
      sort,
      direction,
    });
  });
}

async function getRepo(token, owner, repo) {
  return withRetry(async () => {
    const octo = client(token);
    const { data } = await octo.repos.get({ owner, repo });
    return data;
  });
}

async function createRepo(token, { name, isPrivate, description }) {
  return withTimeout((async () => {
    const octo = client(token);
    const { data } = await octo.repos.createForAuthenticatedUser({
      name,
      private: isPrivate,
      description: description || undefined,
      auto_init: true, // ensures a default branch + initial commit exist immediately
    });
    return data;
  })(), 'Create repo');
}

async function deleteRepo(token, owner, repo) {
  return withTimeout((async () => {
    const octo = client(token);
    await octo.repos.delete({ owner, repo });
  })(), 'Delete repo');
}

async function renameRepo(token, owner, repo, newName) {
  return withTimeout((async () => {
    const octo = client(token);
    const { data } = await octo.repos.update({ owner, repo, name: newName });
    return data;
  })(), 'Rename repo');
}

async function setVisibility(token, owner, repo, isPrivate) {
  return withTimeout((async () => {
    const octo = client(token);
    const { data } = await octo.repos.update({ owner, repo, private: isPrivate });
    return data;
  })(), 'Change visibility');
}

async function forkRepo(token, owner, repo) {
  return withTimeout((async () => {
    const octo = client(token);
    const { data } = await octo.repos.createFork({ owner, repo });
    return data;
  })(), 'Fork repo');
}

/** Full recursive file tree — used for both Browse Files and file search */
async function getTree(token, owner, repo, branch = null) {
  return withRetry(async () => {
    const octo = client(token);
    const repoData = branch ? { default_branch: branch } : await getRepo(token, owner, repo);
    const { data: refData } = await octo.git.getRef({
      owner,
      repo,
      ref: `heads/${repoData.default_branch}`,
    });
    const { data } = await octo.git.getTree({
      owner,
      repo,
      tree_sha: refData.object.sha,
      recursive: 'true',
    });
    return data.tree.filter((entry) => entry.type === 'blob'); // files only
  });
}

async function getFileContent(token, owner, repo, path) {
  return withRetry(async () => {
    const octo = client(token);
    const { data } = await octo.repos.getContent({ owner, repo, path });
    if (Array.isArray(data)) throw new Error('Path is a directory, not a file');
    const content = Buffer.from(data.content, data.encoding).toString('utf8');
    return { content, sha: data.sha, size: data.size };
  });
}

/**
 * Create or update a single file — one commit per call.
 * For multi-file zip uploads, use commitMultipleFiles() instead (one commit total).
 */
async function putFile(token, owner, repo, path, content, message, existingSha = null) {
  return withTimeout((async () => {
    const octo = client(token);
    const { data } = await octo.repos.createOrUpdateFileContents({
      owner,
      repo,
      path,
      message,
      content: Buffer.from(content, 'utf8').toString('base64'),
      sha: existingSha || undefined,
    });
    return data;
  })(), 'Update file');
}

async function deleteFile(token, owner, repo, path, sha, message) {
  return withTimeout((async () => {
    const octo = client(token);
    const { data } = await octo.repos.deleteFile({ owner, repo, path, message, sha });
    return data;
  })(), 'Delete file');
}

/**
 * Commit multiple files (and optionally delete some) in ONE commit using the
 * Git Data API (blobs -> tree -> commit -> update ref). Deletions are done by
 * setting `sha: null` on that path's tree entry, which GitHub's Git Trees API
 * treats as "remove this path" when building on top of an existing base_tree.
 *
 * Given a large batch/zip can genuinely need several sequential API calls,
 * this gets a longer timeout window than the single-call operations above —
 * still bounded, just sized for what a real multi-file commit can take.
 */
async function commitMultipleFiles(token, owner, repo, files, message, deletions = []) {
  return Promise.race([
    (async () => {
      const octo = client(token);
      const repoData = await getRepo(token, owner, repo);
      const branch = repoData.default_branch;

      const { data: refData } = await octo.git.getRef({ owner, repo, ref: `heads/${branch}` });
      const latestCommitSha = refData.object.sha;

      const { data: latestCommit } = await octo.git.getCommit({
        owner,
        repo,
        commit_sha: latestCommitSha,
      });
      const baseTreeSha = latestCommit.tree.sha;

      const blobs = await Promise.all(
        files.map(async (f) => {
          const { data: blob } = await octo.git.createBlob({
            owner,
            repo,
            content: Buffer.from(f.content).toString('base64'),
            encoding: 'base64',
          });
          return { path: f.path, mode: '100644', type: 'blob', sha: blob.sha };
        })
      );

      const deletionEntries = deletions.map((path) => ({ path, mode: '100644', type: 'blob', sha: null }));

      const { data: newTree } = await octo.git.createTree({
        owner,
        repo,
        base_tree: baseTreeSha,
        tree: [...blobs, ...deletionEntries],
      });

      const { data: newCommit } = await octo.git.createCommit({
        owner,
        repo,
        message,
        tree: newTree.sha,
        parents: [latestCommitSha],
      });

      await octo.git.updateRef({ owner, repo, ref: `heads/${branch}`, sha: newCommit.sha });

      return newCommit;
    })(),
    new Promise((_, reject) => setTimeout(() => reject(new Error('Commit timed out after 45000ms')), 45000)),
  ]);
}

/** Codeload zip URL — kept for reference/fallback links in error messages only */
function zipDownloadUrl(owner, repo, branch = 'main') {
  return `https://github.com/${owner}/${repo}/archive/refs/heads/${branch}.zip`;
}

/**
 * Downloads a repo archive as a Buffer using the authenticated Git Archive API.
 * Unlike a plain fetch() against github.com/.../archive/...zip (which returns a
 * 9-byte "Not Found" for any private repo since it isn't authenticated), this
 * goes through Octokit with the user's token and works for private AND public repos.
 */
async function downloadZip(token, owner, repo, ref) {
  return withTimeout((async () => {
    const octo = client(token);
    const response = await octo.repos.downloadZipballArchive({ owner, repo, ref });
    return Buffer.from(response.data);
  })(), 'Download zip');
}

/** Fetches per-language byte counts (used to compute language % breakdown) */
async function getLanguages(token, owner, repo) {
  return withRetry(async () => {
    const octo = client(token);
    const { data } = await octo.repos.listLanguages({ owner, repo });
    return data; // { JavaScript: 12345, HTML: 6789, ... } bytes per language
  });
}

module.exports = {
  getAuthenticatedUser,
  getRateLimit,
  listRepos,
  getRepo,
  createRepo,
  deleteRepo,
  renameRepo,
  setVisibility,
  forkRepo,
  getTree,
  getFileContent,
  putFile,
  deleteFile,
  commitMultipleFiles,
  zipDownloadUrl,
  downloadZip,
  getLanguages,
  isRateLimitError,
};
