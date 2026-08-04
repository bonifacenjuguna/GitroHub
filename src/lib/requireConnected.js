const users = require('./users');
const oauth = require('./oauth');
const inline = require('../keyboards/inline');

/**
 * Guard used at the top of every handler that touches GitHub.
 * Returns the decrypted token if connected, otherwise sends the
 * connect prompt and returns null so the caller can bail out.
 */
async function requireConnected(ctx) {
  const telegramId = ctx.from.id;
  const connected = await users.isConnected(telegramId);

  if (!connected) {
    const url = oauth.buildAuthorizeUrl(telegramId);
    await ctx.reply(
      '🔒 You need to connect your GitHub account first.',
      inline.connectButton(url)
    );
    return null;
  }

  return users.getDecryptedToken(telegramId);
}

module.exports = requireConnected;
