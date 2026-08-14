const users = require('../lib/users');
const repoCache = require('../lib/repoCache');
const oauth = require('../lib/oauth');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const config = require('../config');
const format = require('../lib/format');

/**
 * Shared "you need to connect" prompt — used by /start, requireConnected(),
 * Settings, Disconnect, and the "🔗 Connect GitHub" BBTB button, so every
 * entry point shows the exact same message and resets the BBTB to the
 * disconnected-state bar (per the "distinct disconnected flow" rule).
 *
 * `showVersion` is only true when called directly from /start — so you can
 * always confirm a deploy actually landed without checking Railway, without
 * cluttering every mid-flow "you need to connect" interruption with it too.
 */
async function sendConnectPrompt(ctx, { intro, showVersion = false } = {}) {
  const telegramId = ctx.from.id;
  const url = oauth.buildAuthorizeUrl(telegramId);
  const versionLine = showVersion ? `\n\n🔧 v${format.escapeMd(config.BOT_VERSION)}` : '';

  await ctx.reply('🔒 Not connected', bbtb.disconnected);
  await ctx.reply(
    (intro ||
      '👋 *Welcome to GitroHub*\n' +
      'Your GitHub, right inside Telegram\\.\n\n' +
      'Create, manage, upload, and download repositories\n' +
      '— all without leaving this chat\\.\n\n' +
      '🔒 Not connected yet\n' +
      'Link your GitHub account to get started\\.') + versionLine,
    { parse_mode: 'MarkdownV2', ...inline.connectButton(url) }
  );
}

async function handleStart(ctx) {
  const telegramId = ctx.from.id;
  const connected = await users.isConnected(telegramId);

  if (!connected) {
    return sendConnectPrompt(ctx, { showVersion: true });
  }

  const user = await users.getUser(telegramId);

  // Repo count is a nice-to-have on the welcome message, not essential —
  // race it against a short timeout so /start can never hang waiting on
  // GitHub even if that call is slow, regardless of what's happening
  // elsewhere.
  let repoCountLine = '';
  try {
    const token = await users.getDecryptedToken(telegramId);
    const repos = await Promise.race([
      repoCache.getRepos(ctx.from.id, token),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 4000)),
    ]);
    repoCountLine = `\n📁 ${repos.length} repos ready to manage`;
  } catch (_) {
    // best-effort — don't block the welcome message if this fails or is slow
  }

  await ctx.reply(
    `👋 Welcome back, @${user.github_username}\n` +
    `🟢 GitHub connected${repoCountLine}\n\n` +
    `Tap a button below to get started.\n\n` +
    `🔧 v${config.BOT_VERSION}`,
    bbtb.mainMenu
  );
}

module.exports = { handleStart, sendConnectPrompt };
