/**
 * Telegram limits callback_data to 64 bytes. Several inline buttons need to
 * carry a full repo file path (Browse Files' folder/file rows, File
 * Actions, Delete confirm, "Replace" lock-path, etc.) — a sufficiently
 * long or deeply-nested path can silently exceed that limit and break the
 * keyboard (Telegram just rejects the button, or the whole sendMessage,
 * depending on how far over).
 *
 * Root fix: never put a raw path in callback_data. Hand out a short
 * opaque token instead and resolve it back to the real path server-side,
 * via the person's own session (Redis-backed, so it survives restarts
 * like the rest of ctx.session).
 *
 * Bounded so a very long-lived session can't grow this without limit —
 * once the map hits MAX_TOKENS, it's reset. A stale button tap after that
 * (extremely unlikely in practice — it'd mean tapping a button from many
 * hundreds of screens ago) just fails to resolve, and callers show a
 * clear "that button expired, navigate there again" message instead of
 * silently resolving to the wrong file.
 */
const MAX_TOKENS = 300;

function store(ctx) {
  ctx.session = ctx.session || {};
  if (!ctx.session.pathTokens) ctx.session.pathTokens = { nextId: 1, map: {} };
  return ctx.session.pathTokens;
}

/** Returns a short id (base36 counter) that resolve() can turn back into `path`. */
function tokenize(ctx, path) {
  const s = store(ctx);
  if (Object.keys(s.map).length >= MAX_TOKENS) {
    s.map = {};
    s.nextId = 1;
  }
  const id = (s.nextId++).toString(36);
  s.map[id] = path;
  return id;
}

/** Returns the original path for a token, or undefined if it's unknown/expired. */
function resolve(ctx, id) {
  const s = store(ctx);
  return Object.prototype.hasOwnProperty.call(s.map, id) ? s.map[id] : undefined;
}

module.exports = { tokenize, resolve };
