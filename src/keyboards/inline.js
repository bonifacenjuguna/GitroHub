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
  [Markup.button.callback('🏷️ By Tag ▾', 'filter:tagmenu'), Markup.button.callback('💻 By Language ▾', 'filter:langmenu')],
  [Markup.button.callback('⬅️ Back', 'repos:back')],
]);

const sortMenu = Markup.inlineKeyboard([
  [Markup.button.callback('🕒 Recently Updated', 'sort:updated')],
  [Markup.button.callback('🔤 Name (A-Z)', 'sort:name')],
  [Markup.button.callback('⭐ Most Stars', 'sort:stars')],
  [Markup.button.callback('📅 Recently Created', 'sort:created')],
  [Markup.button.callback('💻 Dominant Language (A-Z)', 'sort:language')],
  [Markup.button.callback('⬅️ Back', 'repos:back')],
]);

/** Repo View info card — Rename, Pin/Unpin, Tags stay inline; Delete Repo is the destructive one */
function repoActions(repoName, pinned = false) {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback('✏️ Rename', `repo:rename:${repoName}`),
      Markup.button.callback('✏️ Description', `repo:description:${repoName}`),
    ],
    [
      Markup.button.callback(pinned ? '📌 Unpin' : '📌 Pin', `repo:pin:${repoName}`),
      Markup.button.callback('🏷️ Tags', `repo:tags:${repoName}`),
    ],
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
/** Folder/file tree navigator — folders and files rendered as rows, with pagination for large folders */
function fileTree(entries, currentPath, pagination = null) {
  const rows = entries.map((e) => {
    const label = e.type === 'tree' ? `📁 ${e.name}/` : `📄 ${e.name}`;
    const action = e.type === 'tree' ? `browse:dir:${e.path}` : `browse:file:${e.path}`;
    return [Markup.button.callback(label, action)];
  });

  if (pagination && pagination.totalPages > 1) {
    const nav = [];
    if (pagination.page > 1) nav.push(Markup.button.callback('⬅️ Prev', `browse:dirpage:${pagination.page - 1}:${currentPath}`));
    if (pagination.page < pagination.totalPages) nav.push(Markup.button.callback('Next ➡️', `browse:dirpage:${pagination.page + 1}:${currentPath}`));
    if (nav.length) rows.push(nav);
  }

  if (currentPath) {
    const parent = currentPath.split('/').slice(0, -1).join('/');
    rows.push([Markup.button.callback('⬅️ Up One Level', `browse:dir:${parent}`)]);
  }
  return Markup.inlineKeyboard(rows);
}

function fileActions(path) {
  return Markup.inlineKeyboard([
    [Markup.button.callback('👁 View Content', `file:view:${path}`), Markup.button.callback('📥 Send as File', `file:raw:${path}`)],
    [Markup.button.callback('✏️ Edit', `file:edit:${path}`), Markup.button.callback('🔁 Replace', `file:replace:${path}`)],
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
  // Access Log relocated here from its own Settings BBTB row (#47) — same
  // content/flow as before, just reachable from inside Activity now.
  // Refresh relocated here too (#49), same chained-fresh-message pattern
  // as Settings' Refresh Status, instead of its own BBTB row that (per a
  // v0.8.1 audit) was actually colliding with My Repos' Refresh button.
  rows.push([
    Markup.button.callback('🔑 Access Log', 'activity:accesslog'),
    Markup.button.callback('🔄 Refresh', `activity:refresh:${errorsOnly}`),
  ]);
  return Markup.inlineKeyboard(rows);
}

/** v0.8.0 search split — two explicit entry points instead of one box that
 * guessed intent from the input (fuzzy name vs pasted URL). */
function searchTypeMenu() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📁 My Repos', 'search:type:myrepos')],
    [Markup.button.callback('🌐 Public Repo', 'search:type:public')],
  ]);
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
  searchTypeMenu,
};
