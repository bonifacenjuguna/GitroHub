'use strict';

const { InlineKeyboard } = require('grammy');
const { ping: pgPing } = require('../../db/postgres/pool');
const { ping: redisPing } = require('../../db/redis/client');
const { getUser } = require('../../db/postgres/users');
const { getRateLimitSnapshot } = require('../../db/redis/cache');
const { listPulls } = require('../../github/pullRequests');
const { listIssues } = require('../../github/issues');
const pkg = require('../../../package.json');

const START_TIME = Date.now();
let commitHash = 'unknown';
try {
  commitHash = require('child_process')
    .execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] })
    .toString()
    .trim();
} catch (_) {
  // Not a git checkout (e.g. Railway's Nixpacks build) — fine, just falls back to 'unknown'.
}

function uptimeString() {
  const ms = Date.now() - START_TIME;
  const days = Math.floor(ms / 86400000);
  const hours = Math.floor((ms % 86400000) / 3600000);
  const mins = Math.floor((ms % 3600000) / 60000);
  return `${days}d ${hours}h ${mins}m`;
}

function registerUtilityCommands(bot) {
  bot.command('ping', async (ctx) => {
    const start = Date.now();
    const [pgMs, redisMs] = await Promise.all([pgPing().catch(() => -1), redisPing().catch(() => -1)]);
    const telegramMs = Date.now() - start;
    await ctx.reply(
      `🏓 Pong!\n\nBot response: ${telegramMs}ms\nDatabase: ${pgMs}ms\nRedis: ${redisMs}ms\n\nAll systems responsive.`
    );
  });

  bot.command('version', async (ctx) => {
    await ctx.reply(
      `📦 GitroHub v${pkg.version}\n\nCommit: ${commitHash}\nBuilt for Node.js ${process.version}\n\nSee CHANGELOG.md for full release history.`
    );
  });

  bot.command('uptime', async (ctx) => {
    await ctx.reply(`⏱️ Uptime\n\nCurrent session: ${uptimeString()}`);
  });

  bot.command('whoami', async (ctx) => {
    const user = await getUser(ctx.from.id);
    let body = `👤 Account Overview\n\nTelegram\n   Name: ${ctx.from.first_name} ${ctx.from.last_name || ''}\n   Username: @${ctx.from.username || '—'}\n   ID: ${ctx.from.id}\n\n`;
    if (user?.github_username) {
      body += `GitHub\n   Username: @${user.github_username}\n   Connected: ${new Date(user.connected_at).toLocaleDateString()}\n   Token: 🔒 encrypted, valid\n   Scopes: ${user.token_scopes}\n\n`;
      body += `🛡️ PIN Lock: ${user.pin_hash ? 'Enabled' : 'Disabled'}`;
    } else {
      body += `GitHub: not connected`;
    }
    await ctx.reply(body);
  });

  bot.command('health', async (ctx) => {
    const results = { github: '⚠️ untested', pg: '❌', redis: '❌' };
    try {
      const pgMs = await pgPing();
      results.pg = `✅ ${pgMs}ms`;
    } catch (_) { results.pg = '❌ connection failed'; }
    try {
      const redisMs = await redisPing();
      results.redis = `✅ ${redisMs}ms`;
    } catch (_) { results.redis = '❌ connection failed'; }

    const allOk = results.pg.startsWith('✅') && results.redis.startsWith('✅');
    await ctx.reply(
      `🩺 System Health\n\n` +
        `${results.pg.startsWith('✅') ? '✅' : '❌'} PostgreSQL — ${results.pg.replace(/^✅ |^❌ /, '')}\n` +
        `${results.redis.startsWith('✅') ? '✅' : '❌'} Redis — ${results.redis.replace(/^✅ |^❌ /, '')}\n\n` +
        `📊 Process\n   Uptime: ${uptimeString()}\n   Memory: ${Math.round(process.memoryUsage().rss / 1024 / 1024)}MB\n   Version: v${pkg.version} (${commitHash})\n\n` +
        `${allOk ? 'All systems operational.' : '⚠️ One or more systems degraded.'}`
    );
  });

  bot.command('status', async (ctx) => {
    const user = await getUser(ctx.from.id);
    if (!user?.github_username) {
      return ctx.reply('📊 GitroHub Status\n\nGitHub not connected yet. Use /menu → 🔐 Account & Security to connect.');
    }
    const reposApi = require('../../github/repos');
    const repos = await reposApi.listRepos(ctx.from.id, { perPage: 1 }).catch(() => []);
    const rateLimit = await getRateLimitSnapshot(ctx.from.id);
    let body = `📊 GitroHub Status\n\n👤 ${ctx.from.first_name}\n🔗 GitHub: @${user.github_username} ✅\n\n`;
    if (rateLimit) body += `📊 GitHub API: ${rateLimit.remaining} / ${rateLimit.limit} remaining\n   Resets ${new Date(rateLimit.resetsAt).toLocaleTimeString()}\n\n`;
    body += `🕐 Last activity check via /status`;
    await ctx.reply(body);
  });

  bot.command('cancel', async (ctx) => {
    ctx.session.pendingAction = null;
    ctx.session.uploadState = null;
    await ctx.reply('✅ Cancelled. Returning to Main Menu.');
    const { renderMainMenu } = require('../menus/mainMenu');
    await renderMainMenu(ctx);
  });

  bot.command('security', async (ctx) => {
    const { renderSecurityMenu } = require('../menus/security');
    await renderSecurityMenu(ctx);
  });

  bot.command('settings', async (ctx) => {
    const { renderSettingsMenu } = require('../menus/settings');
    await renderSettingsMenu(ctx);
  });

  bot.command('upload', async (ctx) => {
    const { registerUploadMenu } = require('../menus/upload');
    const kb = new InlineKeyboard().text('📄 Single File', 'upload:target:file').text('📦 ZIP Project', 'upload:target:zip');
    await ctx.reply('📁 Upload / Deploy\n\nWhat do you want to upload?', { reply_markup: kb });
  });

  bot.command('pr', async (ctx) => {
    const user = await getUser(ctx.from.id);
    if (!user?.github_username) return ctx.reply('Connect GitHub first via /security');
    await ctx.reply('🔀 Fetching your open PRs across repos... (use 🔍 Search Code → Pull Requests in /menu for the full cross-repo view)');
  });

  bot.command('repo', async (ctx) => {
    const arg = ctx.match?.trim();
    if (!arg || !arg.includes('/')) {
      return ctx.reply('❌ Usage: /repo owner/name\n\nExample: /repo torvalds/linux');
    }
    const { renderRepoDetail } = require('../menus/repoDetail');
    await renderRepoDetail(ctx, arg);
  });

  bot.command('clone', async (ctx) => {
    const url = ctx.match?.trim();
    if (!url) return ctx.reply('❌ Usage: /clone <github-url>');
    await ctx.reply(`🔗 Detected: ${url}\n\nUse the paste-a-URL flow for the full fork/download options.`);
  });

  bot.command('help', async (ctx) => {
    const { renderHelpMenu } = require('../menus/help');
    await renderHelpMenu(ctx);
  });
}

module.exports = { registerUtilityCommands };
