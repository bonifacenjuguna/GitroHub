'use strict';

const { InlineKeyboard } = require('grammy');
const { getUser } = require('../../db/postgres/users');
const { getPreferences, updatePreference } = require('../../db/postgres/preferences');

async function renderSettingsMenu(ctx) {
  const user = await getUser(ctx.from.id);
  const prefs = await getPreferences(ctx.from.id);
  const body =
    `⚙️ Settings\n\n` +
    `👤 @${ctx.from.username || ctx.from.first_name}\n` +
    `🌐 Language: ${prefs.language} · 🕐 Timezone: ${prefs.timezone}`;

  const kb = new InlineKeyboard()
    .text('👤 Account', 'settings:account').row()
    .text('🔔 Notifications', 'settings:notifications').row()
    .text('🎨 Display & Interface', 'settings:display').row()
    .text('📦 Default Repo Behavior', 'settings:defaults').row()
    .text('⌨️ Commands & Shortcuts', 'settings:shortcuts').row()
    .text('💾 Data & Storage', 'settings:data').row()
    .text('⬅️ Back to Menu', 'menu:main');

  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderAccountSettings(ctx) {
  const user = await getUser(ctx.from.id);
  const body =
    `👤 Account\n\n` +
    `Telegram: @${ctx.from.username || '—'} (ID: ${ctx.from.id})\n` +
    `GitHub: ${user.github_username ? '@' + user.github_username + ' (connected ✅)' : 'not connected'}\n` +
    `📅 Member since: ${new Date(user.created_at).toLocaleDateString()}`;
  const kb = new InlineKeyboard()
    .text('📝 GitHub Profile', 'settings:profile').row()
    .text('🔗 Manage GitHub Connection →', 'menu:security').row()
    .text('🗑️ Delete My GitroHub Account', 'settings:delete_account:confirm').row()
    .text('⬅️ Back to Settings', 'menu:settings');
  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderDisplaySettings(ctx) {
  const prefs = await getPreferences(ctx.from.id);
  const body = `🎨 Display & Interface\n\nRepo list view: ${prefs.list_view_style}\nDiff style: ${prefs.diff_style}\nEmoji density: ${prefs.emoji_density}\nDate format: ${prefs.date_format}`;
  const kb = new InlineKeyboard()
    .text(`📋 List View: ${prefs.list_view_style}`, 'settings:cycle:list_view_style').row()
    .text(`📄 Diff Style: ${prefs.diff_style}`, 'settings:cycle:diff_style').row()
    .text(`😀 Emoji: ${prefs.emoji_density}`, 'settings:cycle:emoji_density').row()
    .text(`🕐 Dates: ${prefs.date_format}`, 'settings:cycle:date_format').row()
    .text('⬅️ Back to Settings', 'menu:settings');
  await ctx.editOrReply(body, { reply_markup: kb });
}

const CYCLE_OPTIONS = {
  list_view_style: ['cards', 'compact'],
  diff_style: ['unified', 'split'],
  emoji_density: ['full', 'minimal', 'off'],
  date_format: ['relative', 'absolute'],
};

function registerSettingsMenu(bot) {
  bot.callbackQuery('menu:settings', async (ctx) => {
    await renderSettingsMenu(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:account', async (ctx) => {
    await renderAccountSettings(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:display', async (ctx) => {
    await renderDisplaySettings(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^settings:cycle:(.+)$/, async (ctx) => {
    const field = ctx.match[1];
    const prefs = await getPreferences(ctx.from.id);
    const options = CYCLE_OPTIONS[field];
    const currentIndex = options.indexOf(prefs[field]);
    const next = options[(currentIndex + 1) % options.length];
    await updatePreference(ctx.from.id, field, next);
    await renderDisplaySettings(ctx);
    await ctx.answerCallbackQuery(`Set to ${next}`);
  });

  bot.callbackQuery('settings:notifications', async (ctx) => {
    const prefs = await getPreferences(ctx.from.id);
    const kb = new InlineKeyboard()
      .text(`🔊 All Notifications: ${prefs.notifications_enabled ? 'ON' : 'OFF'}`, 'settings:toggle:notifications_enabled').row()
      .text('⬅️ Back to Settings', 'menu:settings');
    await ctx.editOrReply('🔔 Notification Preferences', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:toggle:notifications_enabled', async (ctx) => {
    const prefs = await getPreferences(ctx.from.id);
    await updatePreference(ctx.from.id, 'notifications_enabled', !prefs.notifications_enabled);
    await ctx.answerCallbackQuery('Updated');
    const kb = new InlineKeyboard()
      .text(`🔊 All Notifications: ${!prefs.notifications_enabled ? 'ON' : 'OFF'}`, 'settings:toggle:notifications_enabled').row()
      .text('⬅️ Back to Settings', 'menu:settings');
    await ctx.editOrReply('🔔 Notification Preferences', { reply_markup: kb });
  });

  bot.callbackQuery('settings:defaults', async (ctx) => {
    const prefs = await getPreferences(ctx.from.id);
    const body = `📦 Default Repo Behavior\n\nNew repos default to:\n${prefs.default_repo_visibility === 'private' ? '🔒' : '🌐'} ${prefs.default_repo_visibility}\n📄 README: ${prefs.default_readme ? 'Yes' : 'No'}\n🚫 .gitignore: ${prefs.default_gitignore_template}\n⚖️ License: ${prefs.default_license}`;
    const kb = new InlineKeyboard().text('⬅️ Back to Settings', 'menu:settings');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:shortcuts', async (ctx) => {
    const { query } = require('../../db/postgres/pool');
    const result = await query('SELECT * FROM custom_shortcuts WHERE telegram_user_id = $1', [ctx.from.id]);
    let body = `⌨️ Commands & Shortcuts\n\n/repo owner/name — jump to a repo\n/pr — your open PRs\n/upload — jump to upload\n/status — quick summary\n\n📌 Custom Shortcuts (${result.rows.length}/5)\n`;
    result.rows.forEach((s) => (body += `/${s.command} → ${s.action_type}\n`));
    const kb = new InlineKeyboard().text('⬅️ Back to Settings', 'menu:settings');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:data', async (ctx) => {
    const body = `💾 Data & Storage\n\nGitroHub does not permanently store your source code — uploaded files are processed and committed immediately, never retained.`;
    const kb = new InlineKeyboard().text('⬅️ Back to Settings', 'menu:settings');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:delete_account:confirm', async (ctx) => {
    const kb = new InlineKeyboard().text('✅ Yes, Delete Everything', 'settings:delete_account:execute').text('❌ Cancel', 'settings:account');
    await ctx.editOrReply(
      `⚠️ Delete Your GitroHub Account?\n\nThis will permanently delete your encrypted GitHub token and all stored preferences. This will NOT delete anything on GitHub itself. This cannot be undone.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('settings:delete_account:execute', async (ctx) => {
    const { query } = require('../../db/postgres/pool');
    await query('DELETE FROM users WHERE telegram_user_id = $1', [ctx.from.id]);
    await ctx.editOrReply('✅ Your GitroHub account and all data have been permanently erased.');
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerSettingsMenu, renderSettingsMenu };
