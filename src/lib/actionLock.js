/**
 * Prevents a destructive action from running twice if the person double-taps
 * a button (network lag, impatience) before the first tap's response comes
 * back. Single-user bot, so a simple in-process Set is enough — no need for
 * anything Redis-backed or cross-process.
 *
 * Keyed by `${telegramId}:${actionKey}`, not just telegramId — a lock
 * scoped to the whole user would block two genuinely unrelated actions
 * from ever overlapping (e.g. Delete Repo on one repo blocking a Fork on a
 * completely different one), which isn't what this is for. Only a second
 * tap of the SAME action should be blocked.
 *
 * IMPORTANT: `actionKey` must scope down to the actual TARGET too, not
 * just the action type. A key like just 'deleteRepo' means deleting repo
 * A and immediately deleting repo B (two genuinely unrelated actions)
 * would incorrectly block each other, contradicting the paragraph above —
 * every call site should key on `${actionType}:${target}` (e.g.
 * `deleteRepo:${repoName}`, `editFile:${repoName}:${filePath}`) whenever
 * the action applies to a specific resource. Only truly global,
 * singleton actions (disconnect, a whole bulk-selection run) should use a
 * bare action-type key with no target.
 */
const locked = new Set();

function tryAcquire(key) {
  if (locked.has(key)) return false;
  locked.add(key);
  return true;
}

function release(key) {
  locked.delete(key);
}

/** Runs fn only if no matching action is already in flight for this
 * person. `actionKey` scopes the lock (e.g. 'deleteRepo:my-repo') so
 * unrelated actions never block each other. Returns { skipped: true } if
 * a duplicate tap of the SAME action was blocked. */
async function withLock(telegramId, actionKey, fn) {
  const key = `${telegramId}:${actionKey}`;
  if (!tryAcquire(key)) return { skipped: true };
  try {
    await fn();
    return { skipped: false };
  } finally {
    release(key);
  }
}

module.exports = { withLock };
