const { Markup } = require('telegraf');

/** Repo list — each repo is its own tappable row, plus pagination + filter/sort labels */
function repoList(repos, page, totalPages, filterLabel, sortLabel) {
  const rows = repos.map((r) => [Markup.button.callback(`📦 ${r.name}`, `repo:${r.name}`)]);
  const pagination = [];
  if (page > 1) pagination.push(Markup.button.callback('⬅️ Prev', `repos:page:${page - 1}`));
  if (page < totalPages) pagination.push(Markup.button.callback('Next ➡️', `repos:page:${page + 1}`));
  if (pagination.length) rows.push(pagination);
  return Markup.inlineKeyboard(rows);
}

const filterMenu = Markup.inlineKeyboard([
  [Markup.button.callback('All', 'filter:all'), Markup.button.callback('🌐 Public', 'filter:public')],
  [Markup.button.callback('🔒 Private', 'filter:private'), Markup.button.callback('🍴 Forks', 'filter:forks')],
  [Markup.button.callback('⬅️ Back', 'repos:back')],
]);

const sortMenu = Markup.inlineKeyboard([
  [Markup.button.callback('🕒 Recently Updated', 'sort:updated')],
  [Markup.button.callback('🔤 Name (A-Z)', 'sort:name')],
  [Markup.button.callback('⭐ Most Stars', 'sort:stars')],
  [Markup.button.callback('📅 Recently Created', 'sort:created')],
  [Markup.button.callback('⬅️ Back', 'repos:back')],
]);

/** Repo View info card — only Rename + Delete Repo live inline (destructive/specific) */
function repoActions(repoName) {
  return Markup.inlineKeyboard([
    [Markup.button.callback('✏️ Rename', `repo:rename:${repoName}`)],
    [Markup.button.callback('🗑 Delete Repo', `repo:delete:${repoName}`)],
  ]);
}

function deleteRepoConfirm(repoName) {
  return Markup.inlineKeyboard([
    [Markup.button.callback('✅ Yes, Delete', `repo:delete:confirm:${repoName}`)],
    [Markup.button.callback('❌ Cancel', `repo:delete:cancel:${repoName}`)],
  ]);
}

function visibilityConfirm(repoName, currentlyPrivate) {
  const label = currentlyPrivate ? '🌐 Switch to Public' : '🔒 Switch to Private';
  return Markup.inlineKeyboard([
    [Markup.button.callback(label, `repo:visibility:confirm:${repoName}`)],
    [Markup.button.callback('❌ Cancel', `repo:visibility:cancel:${repoName}`)],
  ]);
}

const createRepoVisibility = Markup.inlineKeyboard([
  [Markup.button.callback('🔒 Private', 'create:visibility:private')],
  [Markup.button.callback('🌐 Public', 'create:visibility:public')],
]);

const createRepoConfirm = Markup.inlineKeyboard([
  [Markup.button.callback('✅ Create', 'create:confirm')],
  [Markup.button.callback('❌ Cancel', 'create:cancel')],
]);

const cancelConfirm = (scenePrefix) => Markup.inlineKeyboard([
  [Markup.button.callback('✅ Yes, Cancel', `${scenePrefix}:cancel:confirm`)],
  [Markup.button.callback('⬅️ No, Go Back', `${scenePrefix}:cancel:abort`)],
]);

function createRepoSuccess(repoName) {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📦 Open Repo', `repo:${repoName}`)],
    [Markup.button.callback('⬆️ Upload Files', `upload:start:${repoName}`)],
  ]);
}

/** File/folder tree navigator — folders and files both rendered as rows */
function fileTree(entries, currentPath, showUploadHere = false) {
  const rows = entries.map((e) => {
    const label = e.type === 'tree' ? `📁 ${e.name}/` : `📄 ${e.name}`;
    const action = e.type === 'tree' ? `browse:dir:${e.path}` : `browse:file:${e.path}`;
    return [Markup.button.callback(label, action)];
  });
  if (showUploadHere) rows.push([Markup.button.callback('📌 Upload Here', `upload:path:${currentPath}`)]);
  if (currentPath) {
    const parent = currentPath.split('/').slice(0, -1).join('/');
    rows.push([Markup.button.callback('⬅️ Up One Level', `browse:dir:${parent}`)]);
  }
  return Markup.inlineKeyboard(rows);
}

function fileActions(path) {
  return Markup.inlineKeyboard([
    [Markup.button.callback('👁 View Content', `file:view:${path}`), Markup.button.callback('📥 Send as File', `file:raw:${path}`)],
    [Markup.button.callback('✏️ Edit', `file:edit:${path}`)],
    [Markup.button.callback('🗑 Delete File', `file:delete:${path}`)],
    [Markup.button.callback('⬅️ Back to Folder', `browse:parent:${path}`)],
  ]);
}

function deleteFileConfirm(path) {
  return Markup.inlineKeyboard([
    [Markup.button.callback('✅ Yes, Delete', `file:delete:confirm:${path}`)],
    [Markup.button.callback('❌ Cancel', `file:delete:cancel:${path}`)],
  ]);
}

function uploadPathChoice() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📁 Browse Folders', 'upload:choose:browse')],
    [Markup.button.callback('📍 Root Directory', 'upload:choose:root')],
  ]);
}

function uploadSummaryConfirm() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📋 View File List', 'upload:summary:list')],
    [Markup.button.callback('✅ Commit Changes', 'upload:commit'), Markup.button.callback('❌ Cancel', 'upload:cancel')],
  ]);
}

function externalRepoActions() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('⬇️ Download as ZIP', 'external:download')],
    [Markup.button.callback('🍴 Fork to My Account', 'external:fork')],
    [Markup.button.url('🔗 View on GitHub', '{{url}}')], // url patched by caller
    [Markup.button.callback('⬅️ Cancel', 'external:cancel')],
  ]);
}

function forkConfirm() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('✅ Confirm Fork', 'external:fork:confirm')],
    [Markup.button.callback('❌ Cancel', 'external:fork:cancel')],
  ]);
}

function notificationsMenu(prefs) {
  const check = (b) => (b ? '✅' : '⬜');
  return Markup.inlineKeyboard([
    [Markup.button.callback(`${check(prefs.githubActivity)} GitHub Activity`, 'notif:toggle:githubActivity')],
    [Markup.button.callback(`${check(prefs.systemAlerts)} System Alerts`, 'notif:toggle:systemAlerts')],
    [Markup.button.callback(`${check(prefs.longOps)} Long Operations`, 'notif:toggle:longOps')],
    [Markup.button.callback(`${check(prefs.tokenHealth)} Token Health`, 'notif:toggle:tokenHealth')],
    [Markup.button.callback('⬅️ Back', 'settings:back')],
  ]);
}

function disconnectConfirm() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('✅ Yes, Disconnect', 'settings:disconnect:confirm')],
    [Markup.button.callback('❌ Cancel', 'settings:disconnect:cancel')],
  ]);
}

function connectButton(url) {
  return Markup.inlineKeyboard([[Markup.button.url('🔗 Connect GitHub Account', url)]]);
}

function activityPagination(page, totalPages, errorsOnly) {
  const rows = [];
  const nav = [];
  if (page > 1) nav.push(Markup.button.callback('⬅️ Prev', `activity:page:${page - 1}:${errorsOnly}`));
  if (page < totalPages) nav.push(Markup.button.callback('Next ➡️', `activity:page:${page + 1}:${errorsOnly}`));
  if (nav.length) rows.push(nav);
  rows.push([
    Markup.button.callback(errorsOnly ? '⬅️ Back to Full Log' : '⚠️ Errors Only', `activity:filter:${!errorsOnly}`),
  ]);
  return Markup.inlineKeyboard(rows);
}

module.exports = {
  repoList,
  filterMenu,
  sortMenu,
  repoActions,
  deleteRepoConfirm,
  visibilityConfirm,
  createRepoVisibility,
  createRepoConfirm,
  cancelConfirm,
  createRepoSuccess,
  fileTree,
  fileActions,
  deleteFileConfirm,
  uploadPathChoice,
  uploadSummaryConfirm,
  externalRepoActions,
  forkConfirm,
  notificationsMenu,
  disconnectConfirm,
  connectButton,
  activityPagination,
};
