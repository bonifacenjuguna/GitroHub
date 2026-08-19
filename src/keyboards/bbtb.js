const { Markup } = require('telegraf');

/**
 * BBTB = "Buttons Below the Typing Bar" = Telegram Reply Keyboards.
 *
 * Rule locked during design: BBTB carries frequent/reusable/low-risk
 * actions. Inline keyboards carry content + destructive/final confirms.
 * Every zone below matches what was agreed on screen-by-screen.
 */

const mainMenu = Markup.keyboard([
  ['📁 My Repos', '➕ New Repo'],
  ['🔍 Search Repo', '⚙️ Settings'],
]).resize();

const myRepos = Markup.keyboard([
  ['🔎 Filter', '↕️ Sort', '📊 Stats'],
  ['➕ New Repo', '🔄 Refresh', '⭐ Pinned'],
  ['🧹 Bulk Select', '⬆️ Back to Menu'],
]).resize();

const repoView = Markup.keyboard([
  ['⬆️ Upload', '📁 Browse Files', '⬇️ Download Repo'],
  ['🔒 Visibility', '⚖️ License', '⬅️ Back to Repos'],
  ['⬆️ Back to Menu'],
]).resize();

const browseFiles = Markup.keyboard([
  ['⬆️ Upload Here', '🔁 Replace Folder', '🔍 Search Files'],
  ['⬆️ Back to Repo'],
]).resize();

// Refresh Status (#48) and Access Log (#47) both relocated off this
// keyboard — Refresh is now an inline button on the Settings message
// itself (chained fresh-message pattern), and Access Log is reachable
// from inside Activity instead of its own Settings row.
const settings = Markup.keyboard([
  ['📜 Activity', '⚙️ Defaults', '📦 Storage'],
  ['🚪 Disconnect', '⬆️ Back to Menu'],
]).resize();

const cancelOnly = Markup.keyboard([['❌ Cancel']]).resize();

const cancelWithSkip = Markup.keyboard([
  ['⏭️ Skip', '❌ Cancel'],
]).resize();

const cancelWithBack = Markup.keyboard([
  ['⬅️ Back', '❌ Cancel'],
]).resize();

const uploadSummary = Markup.keyboard([
  ['📤 Upload Another', '⬆️ Back to Repo'],
]).resize();

const searchAgain = Markup.keyboard([
  ['🔁 Search Again', '⬆️ Back to Menu'],
]).resize();

// Refresh relocated to an inline button on the Activity message itself
// (#49, same chained pattern as Settings' Refresh Status).
const activityLog = Markup.keyboard([
  ['⬆️ Back to Settings'],
]).resize();

const disconnected = Markup.keyboard([
  ['🔗 Connect GitHub', '⚙️ Settings'],
]).resize();

// Refresh relocated to an inline button alongside the pin reorder arrows
// (#50, same reasoning as Activity's Refresh above).
const pinned = Markup.keyboard([
  ['⬆️ Back to Menu'],
]).resize();

const bulkSelect = Markup.keyboard([
  ['✅ Done', '❌ Cancel', '⬆️ Menu'],
]).resize();

const bulkActionMenu = Markup.keyboard([
  ['◀️ Selection', '❌ Cancel', '⬆️ Menu'],
]).resize();

const bulkComplete = Markup.keyboard([
  ['📁 My Repos', '⬆️ Menu'],
]).resize();

const backToSettings = Markup.keyboard([
  ['⬆️ Back to Settings'],
]).resize();

const remove = Markup.removeKeyboard();

module.exports = {
  mainMenu,
  myRepos,
  repoView,
  browseFiles,
  settings,
  cancelOnly,
  cancelWithSkip,
  cancelWithBack,
  uploadSummary,
  searchAgain,
  activityLog,
  disconnected,
  pinned,
  bulkSelect,
  bulkActionMenu,
  bulkComplete,
  backToSettings,
  remove,
};
