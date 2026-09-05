/**
 * Ephemeral messages — "flash, then vanish." Generalizes the exact pattern
 * Filter/Sort already used (edit a confirmation, delete it ~800ms later,
 * show the real result underneath) into a reusable helper, so BBTB marker
 * messages and other low-stakes confirmations across the bot can do the
 * same thing instead of piling up forever in the chat.
 *
 * Why this is safe for BBTB markers specifically: a Telegram reply
 * keyboard (BBTB) is a CHAT-level UI element, not tied to the message that
 * introduced it. Once sent, it stays displayed until replaced by another
 * reply keyboard or explicitly removed — deleting the message that
 * carried it does NOT remove the keyboard from view. This is standard,
 * documented Bot API behavior, not something this bot invented.
 *
 * What this is deliberately NOT used for: errors/warnings, anything that
 * functions as a receipt (delete/restore/export results, bulk-run
 * summaries), messages with a document attached, or actual content
 * screens. Those all stay permanent — see the file-by-file call sites for
 * which category each message falls into.
 */

const DEFAULT_DELAY_MS = 2500;

/** Sends a message and schedules its own deletion. Use for BBTB markers
 * and low-stakes confirmations — never for anything the person might want
 * to scroll back to. Failure to delete (message already gone, chat
 * cleared, etc.) is silently ignored — it was only ever a tidiness step,
 * never something the rest of the flow depends on. */
async function sendEphemeral(ctx, text, extra = {}, delayMs = DEFAULT_DELAY_MS) {
  const msg = await ctx.reply(text, extra);
  scheduleDelete(ctx, msg.message_id, delayMs);
  return msg;
}

/** Schedules deletion of an already-sent message by id — for the rarer
 * case where the message itself needs to be built/edited a specific way
 * before it's safe to just fire-and-forget through sendEphemeral. */
function scheduleDelete(ctx, messageId, delayMs = DEFAULT_DELAY_MS) {
  const chatId = ctx.chat.id;
  setTimeout(() => {
    ctx.telegram.deleteMessage(chatId, messageId).catch(() => {});
  }, delayMs).unref();
}

module.exports = { sendEphemeral, scheduleDelete, DEFAULT_DELAY_MS };
