/**
 * Prevents a destructive action from running twice if the person double-taps
 * a button (network lag, impatience) before the first tap's response comes
 * back. Single-user bot, so a simple in-process Set keyed by telegram ID is
 * enough — no need for anything Redis-backed or cross-process.
 */
const locked = new Set();

function tryAcquire(telegramId) {
  if (locked.has(telegramId)) return false;
  locked.add(telegramId);
  return true;
}

function release(telegramId) {
  locked.delete(telegramId);
}

/** Runs fn only if no destructive action is already in flight for this
 * person. Returns { skipped: true } if a duplicate tap was blocked. */
async function withLock(telegramId, fn) {
  if (!tryAcquire(telegramId)) return { skipped: true };
  try {
    await fn();
    return { skipped: false };
  } finally {
    release(telegramId);
  }
}

module.exports = { withLock };
