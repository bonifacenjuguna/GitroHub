const { Octokit } = require('@octokit/rest');

/**
 * Thin wrapper around Octokit implementing every GitHub operation GitroHub's
 * menus map to. One function per bot action, so handlers stay declarative
 * and error-shaping (per our "specific errors always" rule) happens in
 * exactly one place per operation.
 */
function client(token) {
  return new Octokit({ auth: token });
}

async function getAuthenticatedUser(token) {
  const octo = client(token);
  const { data } = await octo.users.getAuthenticated();
  return data; // { login, avatar_url, ... }
}

async function getRateLimit(token) {
  const octo = client(token);
  const { data } = await octo.rateLimit.get();
  return data.resources.core; // { limit, remaining, reset }
}

async function listRepos(token, { sort = 'updated', direction = 'desc' } = {}) {
  const octo = client(token);
  const repos = await octo.paginate(octo.repos.listForAuthenticatedUser, {
    per_page: 100,
    sort,
    direction,
  });
  return repos;
}

async function getRepo(token, owner, repo) {
  const octo = client(token);
  const { data } = await octo.repos.get({ owner, repo });
  return data;
}

async function createRepo(token, { name, isPrivate, description }) {
  const octo = client(token);
  const { data } = await octo.repos.createForAuthenticatedUser({
    name,
    private: isPrivate,
    description: description || undefined,
    auto_init: true, // ensures a default branch + initial commit exist immediately
  });
  return data;
}

async function deleteRepo(token, owner, repo) {
  const octo = client(token);
  await octo.repos.delete({ owner, repo });
}

async function renameRepo(token, owner, repo, newName) {
  const octo = client(token);
  const { data } = await octo.repos.update({ owner, repo, name: newName });
  return data;
}

async function setVisibility(token, owner, repo, isPrivate) {
  const octo = client(token);
  const { data } = await octo.repos.update({ owner, repo, private: isPrivate });
  return data;
}

async function forkRepo(token, owner, repo) {
  const octo = client(token);
  const { data } = await octo.repos.createFork({ owner, repo });
  return data;
}

/** Full recursive file tree — used for both Browse Files and file search */
async function getTree(token, owner, repo, branch = null) {
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
}

async function getFileContent(token, owner, repo, path) {
  const octo = client(token);
  const { data } = await octo.repos.getContent({ owner, repo, path });
  if (Array.isArray(data)) throw new Error('Path is a directory, not a file');
  const content = Buffer.from(data.content, data.encoding).toString('utf8');
  return { content, sha: data.sha, size: data.size };
}

/**
 * Create or update a single file — one commit per call.
 * For multi-file zip uploads, use commitMultipleFiles() instead (one commit total).
 */
async function putFile(token, owner, repo, path, content, message, existingSha = null) {
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
}

async function deleteFile(token, owner, repo, path, sha, message) {
  const octo = client(token);
  const { data } = await octo.repos.deleteFile({ owner, repo, path, message, sha });
  return data;
}

/**
 * Commit multiple files in ONE commit using the Git Data API
 * (blobs -> tree -> commit -> update ref). This is what powers zip uploads
 * with a single combined commit instead of N commits.
 */
async function commitMultipleFiles(token, owner, repo, files, message) {
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

  const { data: newTree } = await octo.git.createTree({
    owner,
    repo,
    base_tree: baseTreeSha,
    tree: blobs,
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
  const octo = client(token);
  const response = await octo.repos.downloadZipballArchive({ owner, repo, ref });
  return Buffer.from(response.data);
}

/** Fetches per-language byte counts (used to compute language % breakdown) */
async function getLanguages(token, owner, repo) {
  const octo = client(token);
  const { data } = await octo.repos.listLanguages({ owner, repo });
  return data; // { JavaScript: 12345, HTML: 6789, ... } bytes per language
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
};
