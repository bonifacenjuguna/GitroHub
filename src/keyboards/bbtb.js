const { Markup } = require('telegraf');
const style = require('./buttonStyle');

/**
 * BBTB = "Buttons Below the Typing Bar" = Telegram Reply Keyboards.
 *
 * Rule locked during design: BBTB carries frequent/reusable/low-risk
 * actions. Inline keyboards carry content + destructive/final confirms.
 * Every zone below matches what was agreed on screen-by-screen.
 *
 * Delete Repo's "Yes, Delete" and "Cancel" are never both red — a color
 * only works as a danger signal if it isn't also used for the safe option.
 * Cancel means exactly one thing everywhere — "the safe way out" — so
 * it's green, not red. Since every actual
 * confirm/cancel PAIR lives in inline keyboards (per the rule above),
 * BBTB never has a true "destructive execute" (red) case either — just
 * Cancel (green) and everything else (blue, the default for
 * frequent/low-risk navigation).
 */
const b = (label) => style.text(label, style.BLUE);
const g = (label) => style.text(label, style.GREEN);

const mainMenu = Markup.keyboard([
  [b('📁 My Repos'), b('➕ New Repo')],
  [b('🔍 Search Repo'), b('⚙️ Settings')],
]).resize();

const myRepos = Markup.keyboard([
  [b('🔎 Filter'), b('↕️ Sort'), b('📊 Stats')],
  [b('➕ New Repo'), b('🔄 Refresh'), b('⭐ Pinned')],
  [b('🧹 Bulk Select'), b('⬆️ Back to Menu')],
]).resize();

const repoView = Markup.keyboard([
  [b('⬆️ Upload'), b('📁 Browse Files'), b('⬇️ Download Repo')],
  [b('🔒 Visibility'), b('⚖️ License'), b('⬅️ Back to Repos')],
  [b('⬆️ Back to Menu')],
]).resize();

const browseFiles = Markup.keyboard([
  [b('⬆️ Upload Here'), b('🔁 Replace Folder'), b('🔍 Search Files')],
  [b('⬆️ Back to Repo')],
]).resize();

// Refresh Status (#48) and Access Log (#47) both relocated off this
// keyboard — Refresh is now an inline button on the Settings message
// itself (chained fresh-message pattern), and Access Log is reachable
// from inside Activity instead of its own Settings row.
const settings = Markup.keyboard([
  [b('📜 Activity'), b('🤖 Automation'), b('📦 Storage')],
  [b('💾 Export/Import'), b('🚪 Disconnect')],
  [b('⬆️ Back to Menu')],
]).resize();

const cancelOnly = Markup.keyboard([[g('❌ Cancel')]]).resize();

const cancelWithSkip = Markup.keyboard([
  [b('⏭️ Skip'), g('❌ Cancel')],
]).resize();

const cancelWithBack = Markup.keyboard([
  [b('⬅️ Back'), g('❌ Cancel')],
]).resize();

const uploadSummary = Markup.keyboard([
  [b('📤 Upload Another'), b('⬆️ Back to Repo')],
]).resize();

const searchAgain = Markup.keyboard([
  [b('🔁 Search Again'), b('⬆️ Back to Menu')],
]).resize();

// Refresh relocated to an inline button on the Activity message itself
// (#49, same chained pattern as Settings' Refresh Status).
const activityLog = Markup.keyboard([
  [b('⬆️ Back to Settings')],
]).resize();

const disconnected = Markup.keyboard([
  [b('🔗 Connect GitHub'), b('⚙️ Settings')],
]).resize();

// Refresh relocated to an inline button alongside the pin reorder arrows
// (#50, same reasoning as Activity's Refresh above).
const pinned = Markup.keyboard([
  [b('⬆️ Back to Menu')],
]).resize();

const bulkSelect = Markup.keyboard([
  [b('✅ Done'), g('❌ Cancel'), b('⬆️ Menu')],
]).resize();

const bulkActionMenu = Markup.keyboard([
  [b('◀️ Selection'), g('❌ Cancel'), b('⬆️ Menu')],
]).resize();

const bulkComplete = Markup.keyboard([
  [b('📁 My Repos'), b('⬆️ Menu')],
]).resize();

// 🤖 Automation hub — mirrors My Repos' 3-row shape: two 3-across rows for
// the sub-sections + frequent actions (equal-weight, not a sequence), then
// a paired action+Back row (same pattern My Repos uses for Bulk Select +
// Back to Menu).
const automation = Markup.keyboard([
  [b('🏷️ Auto-Tag'), b('🔕 Auto-Mute'), b('💾 Auto-Backup')],
  [b('⚙️ Defaults'), b('▶️ Run Rules Now'), b('📜 Log')],
  [b('🗂️ Stale Repos'), b('⬆️ Back to Settings')],
]).resize();

// Auto-Tag Rules and Auto-Mute Rules both nest one level under Automation
// and both want the same "run what I've set up" action close at hand —
// same shape as Browse Files nesting under Repo View.
const automationRules = Markup.keyboard([
  [b('▶️ Run Rules Now')],
  [b('⬆️ Back to Automation')],
]).resize();

// Auto-Backup Rules gets its own "Backup Now" instead of the shared "Run
// Rules Now" — it's a heavier operation (downloads + sends a zip per
// matching repo), so it stays a deliberate, separate tap rather than
// silently riding along with the cheap tag/mute rule run.
const automationBackupRules = Markup.keyboard([
  [b('▶️ Backup Now')],
  [b('⬆️ Back to Automation')],
]).resize();

const backToSettings = Markup.keyboard([
  [b('⬆️ Back to Settings')],
]).resize();

// Nested one level under 🤖 Automation (Defaults, Auto-Tag Rules) — "back"
// from these returns to the Automation hub, not all the way out to
// Settings, matching how Browse Files' "Back to Repo" doesn't jump to Menu.
const backToAutomation = Markup.keyboard([
  [b('⬆️ Back to Automation')],
]).resize();

const exportImport = Markup.keyboard([
  [b('⬆️ Back to Settings')],
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
  backToAutomation,
  automation,
  automationRules,
  automationBackupRules,
  exportImport,
  remove,
};
