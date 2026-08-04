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
  ['➕ New Repo', '🔎 Filter'],
  ['↕️ Sort', '🔄 Refresh'],
  ['⬆️ Back to Menu'],
]).resize();

const repoView = Markup.keyboard([
  ['⬆️ Upload', '📁 Browse Files'],
  ['⬇️ Download Repo', '🔒 Visibility'],
  ['⬅️ Back to Repos', '⬆️ Back to Menu'],
]).resize();

const browseFiles = Markup.keyboard([
  ['🔍 Search Files'],
  ['⬆️ Back to Repo'],
]).resize();

const settings = Markup.keyboard([
  ['🔔 Notifications', '📜 Activity'],
  ['🚪 Disconnect', '🔄 Refresh Status'],
  ['⬆️ Back to Menu'],
]).resize();

const cancelOnly = Markup.keyboard([['❌ Cancel']]).resize();

const cancelWithSkip = Markup.keyboard([
  ['⏭️ Skip', '❌ Cancel'],
]).resize();

const cancelWithBack = Markup.keyboard([
  ['⬅️ Back', '❌ Cancel'],
]).resize();

const uploadSummary = Markup.keyboard([
  ['📤 Upload Another'],
  ['⬆️ Back to Repo'],
]).resize();

const searchAgain = Markup.keyboard([
  ['🔁 Search Again'],
  ['⬆️ Back to Menu'],
]).resize();

const activityLog = Markup.keyboard([
  ['🔄 Refresh'],
  ['⬆️ Back to Settings'],
]).resize();

const disconnected = Markup.keyboard([
  ['🔗 Connect GitHub'],
  ['⚙️ Settings'],
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
  remove,
};
