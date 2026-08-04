const os = require('os');
const github = require('../lib/github');
const users = require('../lib/users');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const pgDb = require('../db/postgres');
const redisDb = require('../db/redis');
const config = require('../config');
const activity = require('../lib/activity');

const startTime = Date.now();

function formatUptime(ms) {
  const sec = Math.floor(ms / 1000);
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

async function showSettings(ctx) {
  const telegramId = ctx.from.id;
  const user = await users.getUser(telegramId);
  const connected = !!(user && user.github_token_enc);

  const [pgStatus, redisStatus] = await Promise.all([pgDb.ping(), redisDb.ping()]);

  let rateLimitLine = 'Not connected';
  if (connected) {
    try {
      const token = await users.getDecryptedToken(telegramId);
      const rl = await github.getRateLimit(token);
      const resetMins = Math.max(0, Math.round((rl.reset * 1000 - Date.now()) / 60000));
      rateLimitLine = `${rl.remaining} / ${rl.limit} remaining \\(resets in ${resetMins}m\\)`;
    } catch (_) {
      rateLimitLine = 'Unable to fetch';
    }
  }

  const mem = process.memoryUsage();
  const memLine = `${Math.round(mem.rss / 1024 / 1024)}MB / ${Math.round(os.totalmem() / 1024 / 1024)}MB`;

  const dbLine = (s) => (s.ok ? `🟢 Connected \\(${s.ms}ms\\)` : `🔴 Unreachable \\(${format.escapeMd(s.error || 'timeout')}\\)`);

  const text =
    `⚙️ *Settings & System Status*\n\n` +
    `👤 *ACCOUNT*\n` +
    `├ GitHub: ${connected ? format.escapeMd(user.github_username) : 'Not connected'}\n` +
    `├ Scope: ${connected ? format.escapeMd(user.github_scope || 'repo') : '—'}\n` +
    `└ Linked since: ${connected ? format.escapeMd(format.relativeTime(user.connected_at)) : '—'}\n\n` +
    `📡 *GITHUB API*\n` +
    `└ Rate limit: ${rateLimitLine}\n\n` +
    `🗄️ *DATABASE*\n` +
    `├ PostgreSQL: ${dbLine(pgStatus)}\n` +
    `└ Redis: ${dbLine(redisStatus)}\n\n` +
    `🖥️ *SYSTEM*\n` +
    `├ Uptime: ${format.escapeMd(formatUptime(Date.now() - startTime))}\n` +
    `├ Host: Railway\n` +
    `├ Memory: ${format.escapeMd(memLine)}\n` +
    `└ Bot version: v${format.escapeMd(config.BOT_VERSION)}`;

  if (!pgStatus.ok) {
    await activity.log(telegramId, '⚠️', 'Postgres unreachable', { detail: pgStatus.error, isError: true }).catch(() => {});
  }

  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...bbtb.settings });
}

async function askDisconnect(ctx) {
  await ctx.reply(
    `⚠️ Disconnect GitHub account\\?\n\n` +
    `This will:\n` +
    `• Remove your stored access token from GitroHub\n` +
    `• Require reconnecting before using any repo features again\n` +
    `• NOT affect anything on GitHub itself \\(no repos deleted\\)`,
    { parse_mode: 'MarkdownV2', ...inline.disconnectConfirm() }
  );
}

async function executeDisconnect(ctx) {
  await users.disconnect(ctx.from.id);
  await activity.log(ctx.from.id, '🚪', 'Disconnected GitHub account');
  const oauth = require('../lib/oauth');
  const url = oauth.buildAuthorizeUrl(ctx.from.id);
  await ctx.reply('✅ Disconnected\\. Your GitHub account is no longer linked\\.', {
    parse_mode: 'MarkdownV2',
    ...inline.connectButton(url),
  });
}

async function showNotifications(ctx) {
  const prefs = await users.getNotificationPrefs(ctx.from.id);
  await ctx.reply(
    `🔔 *Notifications*\n\nChoose what GitroHub should alert you about:`,
    { parse_mode: 'MarkdownV2', ...inline.notificationsMenu(prefs) }
  );
}

async function toggleNotification(ctx, key) {
  await users.toggleNotification(ctx.from.id, key);
  const prefs = await users.getNotificationPrefs(ctx.from.id);
  await ctx.editMessageReplyMarkup(inline.notificationsMenu(prefs).reply_markup);
}

module.exports = { showSettings, askDisconnect, executeDisconnect, showNotifications, toggleNotification };
