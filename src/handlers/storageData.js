const { Markup } = require('telegraf');
const dataStore = require('../lib/dataStore');
const users = require('../lib/users');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');

async function showStorageData(ctx) {
  const counts = await dataStore.getCounts(ctx.from.id);

  const text =
    `📦 *Storage & Data*\n\n` +
    `📌 Pinned repos: ${counts.pinnedRepos}\n` +
    `🏷️ Tags: ${counts.tags}\n` +
    `📜 Activity log: ${counts.activityEntries} entries \\(${counts.activityDays} days\\)\n` +
    `🔐 Encrypted GitHub token: ${counts.hasToken ? '1' : '0'}`;

  const rows = [
    [Markup.button.callback('🗑 Clear Data', 'storage:clearmenu')],
    [Markup.button.callback('⬇️ Export My Data', 'storage:exportmenu')],
    [Markup.button.callback('🧹 Auto-Cleanup Settings', 'storage:cleanupmenu')],
  ];

  await ctx.reply('📦 Storage & Data', bbtb.backToSettings);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function showClearMenu(ctx) {
  await ctx.reply('🗑 What would you like to clear?', Markup.inlineKeyboard([
    [Markup.button.callback('📜 Activity Log', 'storage:clear:activity')],
    [Markup.button.callback('📌 Pins', 'storage:clear:pins')],
    [Markup.button.callback('⚙️ Defaults', 'storage:clear:defaults')],
    [Markup.button.callback('🗑 Everything (Full Reset)', 'storage:clear:full')],
    [Markup.button.callback('⬅️ Back', 'storage:back')],
  ]));
}

async function confirmClear(ctx, scope) {
  if (scope === 'full') {
    ctx.session.awaitingFullReset = true;
    await ctx.reply(
      '⚠️ *Full Reset* — this clears pins, tags, defaults, and activity history\\.\n' +
      'Your GitHub connection stays intact \\(use Disconnect separately for that\\)\\.\n\n' +
      'Type RESET to confirm, or ❌ Cancel\\.',
      { parse_mode: 'MarkdownV2', ...bbtb.cancelOnly }
    );
    return;
  }

  const labels = { activity: 'your Activity Log', pins: 'all Pinned repos', defaults: 'your saved Defaults' };
  await ctx.reply(
    `⚠️ Clear ${labels[scope]}? This cannot be undone.`,
    Markup.inlineKeyboard([
      [Markup.button.callback('✅ Yes, Clear', `storage:doclear:${scope}`)],
      [Markup.button.callback('❌ Cancel', 'storage:back')],
    ])
  );
}

async function executeClear(ctx, scope) {
  const telegramId = ctx.from.id;
  if (scope === 'activity') await dataStore.clearActivityLog(telegramId);
  if (scope === 'pins') await dataStore.clearPins(telegramId);
  if (scope === 'defaults') await dataStore.clearDefaults(telegramId);

  await ctx.reply(format.successMessage(`Cleared ${scope}`));
  return showStorageData(ctx);
}

/** Called from the text router when ctx.session.awaitingFullReset is set */
async function handleResetConfirmationText(ctx) {
  const text = ctx.message.text.trim();
  delete ctx.session.awaitingFullReset;

  if (text === '❌ Cancel') {
    await ctx.reply('Cancelled — nothing was cleared.');
    return showStorageData(ctx);
  }
  if (text !== 'RESET') {
    await ctx.reply(format.errorMessage(
      'Reset not confirmed',
      `you typed "${text}", not "RESET"`,
      'Nothing was cleared. Try again from Storage & Data if you still want to reset.'
    ));
    return showStorageData(ctx);
  }

  await dataStore.fullReset(ctx.from.id);
  await ctx.reply('✅ Full reset complete — pins, tags, defaults, and activity history cleared.');
  return showStorageData(ctx);
}

async function showExportMenu(ctx) {
  await ctx.reply('⬇️ Export format?', Markup.inlineKeyboard([
    [Markup.button.callback('📄 JSON (raw data)', 'storage:export:json')],
    [Markup.button.callback('📋 Readable Summary (.txt)', 'storage:export:txt')],
  ]));
}

async function executeExport(ctx, format_) {
  const content = await dataStore.exportData(ctx.from.id, format_);
  const filename = format_ === 'json' ? 'gitrohub-export.json' : 'gitrohub-export.txt';
  await ctx.replyWithDocument({ source: Buffer.from(content, 'utf8'), filename });
}

async function showCleanupMenu(ctx) {
  const user = await users.getUser(ctx.from.id);
  await ctx.reply(
    `🧹 *Auto\\-Cleanup*\n\n` +
    `Activity Log retention: ${user.activity_retention_days} days\n` +
    `🗑 Auto-delete pins/tags on repo deletion: ${user.auto_cleanup_on_delete ? 'On' : 'Off'}`,
    {
      parse_mode: 'MarkdownV2',
      ...Markup.inlineKeyboard([
        [
          Markup.button.callback('30d', 'storage:retention:30'),
          Markup.button.callback('90d', 'storage:retention:90'),
          Markup.button.callback('1yr', 'storage:retention:365'),
          Markup.button.callback('Forever', 'storage:retention:36500'),
        ],
        [Markup.button.callback(user.auto_cleanup_on_delete ? '🗑 Turn Off Auto-Delete' : '🗑 Turn On Auto-Delete', 'storage:toggleautodelete')],
      ]),
    }
  );
}

async function setRetention(ctx, days) {
  const { pool } = require('../db/postgres');
  await pool.query('UPDATE users SET activity_retention_days = $1 WHERE telegram_id = $2', [Number(days), ctx.from.id]);
  await ctx.reply('✅ Retention updated.');
  return showCleanupMenu(ctx);
}

async function toggleAutoDelete(ctx) {
  const { pool } = require('../db/postgres');
  const user = await users.getUser(ctx.from.id);
  await pool.query('UPDATE users SET auto_cleanup_on_delete = $1 WHERE telegram_id = $2', [!user.auto_cleanup_on_delete, ctx.from.id]);
  return showCleanupMenu(ctx);
}

module.exports = {
  showStorageData,
  showClearMenu,
  confirmClear,
  executeClear,
  handleResetConfirmationText,
  showExportMenu,
  executeExport,
  showCleanupMenu,
  setRetention,
  toggleAutoDelete,
};
