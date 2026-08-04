const users = require('./users');

/**
 * Guard used at the top of every handler that touches GitHub.
 * Returns the decrypted token if connected, otherwise sends the shared
 * connect prompt (which also resets BBTB to the disconnected-state bar,
 * so stale buttons from before a disconnect stop offering dead actions)
 * and returns null so the caller can bail out.
 */
async function requireConnected(ctx) {
  const telegramId = ctx.from.id;
  const connected = await users.isConnected(telegramId);

  if (!connected) {
    // Lazy require to avoid a circular dependency with handlers/start.js
    const { sendConnectPrompt } = require('../handlers/start');
    await sendConnectPrompt(ctx, {
      intro: '🔒 You need to connect your GitHub account first.',
    });
    return null;
  }

  return users.getDecryptedToken(telegramId);
}

module.exports = requireConnected;
