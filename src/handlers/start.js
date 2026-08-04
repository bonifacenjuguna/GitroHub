const users = require('../lib/users');
const oauth = require('../lib/oauth');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');

async function handleStart(ctx) {
  const telegramId = ctx.from.id;
  const connected = await users.isConnected(telegramId);

  if (!connected) {
    const url = oauth.buildAuthorizeUrl(telegramId);
    return ctx.reply(
      '👋 *Welcome to GitroHub*\n' +
      'Your GitHub, right inside Telegram\\.\n\n' +
      'Create, manage, upload, and download repositories\n' +
      '— all without leaving this chat\\.\n\n' +
      '🔒 Not connected yet\n' +
      'Link your GitHub account to get started\\.',
      { parse_mode: 'MarkdownV2', ...inline.connectButton(url) }
    );
  }

  const user = await users.getUser(telegramId);
  await ctx.reply(
    `👋 Welcome back, ${user.github_username}`,
    bbtb.mainMenu
  );
}

module.exports = { handleStart };
