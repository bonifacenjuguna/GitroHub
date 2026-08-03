'use strict';

const { InlineKeyboard } = require('grammy');
const { getUser, disconnectGithub, setPin, clearPin } = require('../../db/postgres/users');
const { createOAuthState, buildAuthorizationUrl, revokeToken } = require('../../security/oauth');
const { getDecryptedToken } = require('../../db/postgres/users');
const { hashPin } = require('../../security/pinLock');
const { logAction, getRecentActivity } = require('../../db/postgres/activityLog');
const { getRateLimitSnapshot } = require('../../db/redis/cache');

async function renderSecurityMenu(ctx) {
  const user = await getUser(ctx.from.id);
  const connected = Boolean(user?.encrypted_token);

  if (!connected) {
    const kb = new InlineKeyboard()
      .text('🔗 Connect GitHub', 'auth:connect').row()
      .text('❓ How is my data secured?', 'security:trust').row()
      .text('⬅️ Back to Menu', 'menu:main');
    return ctx.editOrReply(
      `🔐 Account & Security\n\nYou are not connected to GitHub.\n\nConnecting allows GitroHub to act on your behalf — create/edit repos, push commits, manage PRs, etc., based on the permissions you approve.`,
      { reply_markup: kb }
    );
  }

  const rateLimit = await getRateLimitSnapshot(ctx.from.id);
  let body = `🔐 Account & Security\n\n`;
  body += `✅ Connected as @${user.github_username}\n`;
  body += `🔑 Scopes: ${user.token_scopes || 'unknown'}\n`;
  body += `📅 Connected since: ${new Date(user.connected_at).toLocaleDateString()}\n\n`;
  body += `🔒 Token encrypted with AES-256-GCM\n`;
  body += `🛡️ PIN Lock: ${user.pin_hash ? 'Enabled' : 'Disabled'}\n`;
  if (rateLimit) body += `\n📊 GitHub API: ${rateLimit.remaining} / ${rateLimit.limit} remaining`;

  const kb = new InlineKeyboard()
    .text('🔑 View Permissions', 'security:permissions').row()
    .text('🔁 Reconnect / Re-authorize', 'auth:connect').row()
    .text('📜 Activity Log', 'security:activity').row()
    .text(user.pin_hash ? '🛡️ Disable PIN Lock' : '🛡️ Enable PIN Lock', 'security:pin:toggle').row()
    .text('📊 API Status', 'security:ratelimit').row()
    .text('🗑️ Disconnect GitHub', 'security:disconnect:confirm').row()
    .text('⬅️ Back to Menu', 'menu:main');

  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerSecurityMenu(bot) {
  bot.callbackQuery('menu:security', async (ctx) => {
    await renderSecurityMenu(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('auth:connect', async (ctx) => {
    const state = await createOAuthState(ctx.from.id);
    const url = buildAuthorizationUrl(state);
    const kb = new InlineKeyboard().url('🌐 Open GitHub Authorization', url).row().text('❌ Cancel', 'menu:security');
    await ctx.editOrReply(
      `🔗 Connect Your GitHub Account\n\nTap below to authorize on GitHub. GitroHub never sees or stores your GitHub password.\n\nThis link expires in 5 minutes.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:permissions', async (ctx) => {
    const user = await getUser(ctx.from.id);
    const scopes = (user.token_scopes || '').split(',').map((s) => s.trim()).filter(Boolean);
    let body = `🔑 Current Permissions\n\nGitroHub can currently:\n\n`;
    scopes.forEach((s) => (body += `✅ ${s}\n`));
    body += `\n⚠️ Note: GitHub OAuth scopes are broad by design. Granular per-action permission (like the delete confirmations you see throughout the bot) is enforced by GitroHub itself, not GitHub's scope system.`;
    const kb = new InlineKeyboard().text('🔁 Re-authorize', 'auth:connect').row().text('⬅️ Back to Security', 'menu:security');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:activity', async (ctx) => {
    const entries = await getRecentActivity(ctx.from.id, { limit: 8 });
    let body = `📜 Recent Activity\n\n`;
    if (entries.length === 0) body += 'No recorded activity yet.';
    entries.forEach((e) => {
      body += `${actionIcon(e.action_type)} ${e.action_type.replace(/_/g, ' ')}${e.repo_full_name ? ` — ${e.repo_full_name}` : ''}\n`;
    });
    const kb = new InlineKeyboard().text('⬅️ Back to Security', 'menu:security');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:ratelimit', async (ctx) => {
    const snapshot = await getRateLimitSnapshot(ctx.from.id);
    let body = `📊 GitHub API Status\n\n`;
    if (snapshot) {
      body += `Remaining: ${snapshot.remaining} / ${snapshot.limit}\nResets: ${new Date(snapshot.resetsAt).toLocaleTimeString()}`;
    } else {
      body += `No recent API usage recorded yet — make a request (e.g. open a repo) to populate this.`;
    }
    const kb = new InlineKeyboard().text('⬅️ Back to Security', 'menu:security');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:pin:toggle', async (ctx) => {
    const user = await getUser(ctx.from.id);
    if (user.pin_hash) {
      await clearPin(ctx.from.id);
      await logAction(ctx.from.id, 'pin_disabled');
      await renderSecurityMenu(ctx);
      return ctx.answerCallbackQuery('PIN Lock disabled');
    }
    ctx.session.pendingAction = { type: 'set_pin', payload: {} };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply('🔒 Set a 4-digit PIN\n\nSend 4 digits.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:disconnect:confirm', async (ctx) => {
    const kb = new InlineKeyboard().text('✅ Disconnect', 'security:disconnect:execute').text('❌ Cancel', 'menu:security');
    await ctx.editOrReply(
      `⚠️ Disconnect GitHub?\n\nGitroHub will delete your stored access token immediately and revoke it on GitHub's side. You'll need to reconnect to use the bot again. Your repositories and data on GitHub are NOT affected.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:disconnect:execute', async (ctx) => {
    const token = await getDecryptedToken(ctx.from.id).catch(() => null);
    if (token) await revokeToken(token);
    await disconnectGithub(ctx.from.id);
    require('../../github/client').invalidateClientCache(ctx.from.id);
    await logAction(ctx.from.id, 'disconnect_github');
    const kb = new InlineKeyboard().text('🔗 Reconnect', 'auth:connect').text('🏠 Main Menu', 'menu:main');
    await ctx.editOrReply(`✅ Disconnected. Your GitHub token has been deleted and revoked.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('security:trust', async (ctx) => {
    const kb = new InlineKeyboard().text('⬅️ Back to Security', 'menu:security');
    await ctx.editOrReply(
      `🔒 How GitroHub Secures Your Data\n\n` +
        `• Your GitHub token is encrypted with AES-256-GCM, using a key unique to your account.\n` +
        `• We never store your GitHub password — only an OAuth token, which you can revoke anytime.\n` +
        `• Destructive actions always require explicit confirmation.\n` +
        `• Optional PIN lock adds a second layer for sensitive actions.\n` +
        `• All sensitive actions are logged and viewable in your Activity Log.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });
}

function actionIcon(type) {
  const map = { delete_repo: '🗑️', change_visibility: '🔓', merge_pr: '🔀', push: '📤', disconnect_github: '🔌', pin_disabled: '🛡️' };
  return map[type] || '•';
}

module.exports = { registerSecurityMenu, renderSecurityMenu };
