const { client } = require('../db/redis');
const config = require('../config');

const key = (telegramId) => `wizard:${telegramId}`;

/**
 * Wizard/session state stored in Redis, keyed per Telegram user.
 * This is what makes "⬅️ Back" able to restore previous step data instead
 * of forcing a restart (per our standing UX rule), and lets a half-finished
 * flow survive a bot restart/redeploy on Railway.
 *
 * Shape:
 * {
 *   scene: 'createRepo' | 'uploadFile' | 'renameRepo' | ...,
 *   step: number,
 *   data: { ...collected inputs so far },
 *   history: [ previous step numbers, for Back navigation ],
 *   messageId: number,   // the message we keep editing in place
 *   updatedAt: ISOString
 * }
 */

async function get(telegramId) {
  const raw = await client.get(key(telegramId));
  if (!raw) return null;
  const session = JSON.parse(raw);

  // Auto-expire stale sessions (> TTL) even if Redis TTL somehow didn't fire
  const age = Date.now() - new Date(session.updatedAt).getTime();
  if (age > config.WIZARD_SESSION_TTL_SECONDS * 1000) {
    await clear(telegramId);
    return null;
  }
  return session;
}

async function set(telegramId, session) {
  session.updatedAt = new Date().toISOString();
  await client.set(key(telegramId), JSON.stringify(session), {
    EX: config.WIZARD_SESSION_TTL_SECONDS,
  });
}

async function clear(telegramId) {
  await client.del(key(telegramId));
}

/** Push current step onto history and advance — used for "forward" transitions */
async function advance(telegramId, nextStep, dataPatch = {}) {
  const session = await get(telegramId);
  if (!session) return null;
  session.history.push(session.step);
  session.step = nextStep;
  session.data = { ...session.data, ...dataPatch };
  await set(telegramId, session);
  return session;
}

/** Pop last step from history — used for "⬅️ Back" (preserves session.data) */
async function goBack(telegramId) {
  const session = await get(telegramId);
  if (!session || session.history.length === 0) return null;
  session.step = session.history.pop();
  await set(telegramId, session);
  return session;
}

module.exports = { get, set, clear, advance, goBack };
