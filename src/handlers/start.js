const users = require('../lib/users');
const github = require('../lib/github');
const repoCache = require('../lib/repoCache');
const oauth = require('../lib/oauth');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');

/**
 * Shared "you need to connect" prompt — used by /start, requireConnected(),
 * Settings, Disconnect, and the "🔗 Connect GitHub" BBTB button, so every
 * entry point shows the exact same message and resets the BBTB to the
 * disconnected-state bar (per the "distinct disconnected flow" rule).
 */
async function sendConnectPrompt(ctx, { intro } = {}) {
  const telegramId = ctx.from.id;
  const url = oauth.buildAuthorizeUrl(telegramId);

  await ctx.reply('🔒 Not connected', bbtb.disconnected);
  await ctx.reply(
    intro ||
      '👋 *Welcome to GitroHub*\n' +
      'Your GitHub, right inside Telegram\\.\n\n' +
      'Create, manage, upload, and download repositories\n' +
      '— all without leaving this chat\\.\n\n' +
      '🔒 Not connected yet\n' +
      'Link your GitHub account to get started\\.',
    { parse_mode: 'MarkdownV2', ...inline.connectButton(url) }
  );
}

async function handleStart(ctx) {
  const telegramId = ctx.from.id;
  const connected = await users.isConnected(telegramId);

  if (!connected) {
    return sendConnectPrompt(ctx);
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
    `Tap a button below to get started.`,
    bbtb.mainMenu
  );
}

module.exports = { handleStart, sendConnectPrompt };
