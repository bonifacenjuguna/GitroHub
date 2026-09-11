/**
 * safeEditMessageText — the structural fix for an entire class of crash
 * that used to be patched individually at each call site: Telegram
 * rejects editMessageText with "message is not modified" whenever the
 * new text is identical to what's already there (most commonly a rapid
 * double-tap firing the same edit twice, or a "Refresh" tap when nothing
 * actually changed). That's an expected, routine outcome of editing a
 * message — not a bug condition — so every call to ctx.editMessageText
 * anywhere in this bot should go through here instead of calling it
 * directly, rather than each new screen needing its own try/catch
 * remembered and written correctly by hand.
 *
 * Returns true if the edit went through, false if it was skipped (either
 * because the content was already identical, or the message could no
 * longer be edited for some other reason — e.g. too old, or deleted).
 * Callers with a meaningful fallback (a fresh ctx.reply with the same
 * text) should check the return value and act on false; callers that
 * already have a guaranteed next step regardless (like calling showX(ctx)
 * right after) can safely ignore it.
 */
async function safeEditMessageText(ctx, text, extra) {
  try {
    await ctx.editMessageText(text, extra);
    return true;
  } catch (_) {
    return false;
  }
}

/** Same idea, for the raw Telegram API shape used to edit a message OTHER
 * than the one that triggered the current update — e.g. updating a
 * progress message by its stored message_id during a long-running bulk
 * operation. Same "not modified" tolerance, same true/false contract. */
async function safeEditMessageTextByRef(telegram, chatId, messageId, text, extra) {
  try {
    await telegram.editMessageText(chatId, messageId, undefined, text, extra);
    return true;
  } catch (_) {
    return false;
  }
}

module.exports = { safeEditMessageText, safeEditMessageTextByRef };
