const { Markup } = require('telegraf');
const style = require('../keyboards/buttonStyle');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const scheduledUploads = require('../lib/scheduledUploads');
const timezone = require('../lib/timezone');
const requireConnected = require('../lib/requireConnected');
const ephemeral = require('../lib/ephemeral');

/**
 * 📤 Scheduled Uploads — the view/manage side of the feature; the actual
 * scheduling happens inline in scenes/uploadFile.js's final commit step
 * ("📅 Schedule for Later" alongside "✅ Commit Now"), and execution
 * happens in index.js's poller. Deliberately a separate queue from 🆕
 * Scheduled Repos even though the shape is similar — one creates a repo,
 * this one commits into an EXISTING one, and merging them into one list
 * was confusing enough to be worth two clearly-named screens.
 *
 * Only single-file (or single-archive-as-is) uploads are ever eligible to
 * land here — a multi-file directory sync needs to diff against the
 * repo's LIVE state, which could easily have changed by the time a
 * schedule fires, so that path always commits immediately instead (see
 * scenes/uploadFile.js's eligibility check).
 */
async function showScheduledUploads(ctx) {
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';
  const hour12 = user.time_format === '12h';
  const pending = await scheduledUploads.listPending(ctx.from.id);

  let text = `📤 *Scheduled Uploads*\n\nFiles queued to be committed at a future time — times shown in your timezone \\(${format.escapeMd(tz)}\\)\\.\n\n`;
  text += pending.length === 0
    ? `Nothing scheduled yet\\. Start one from 📤 Upload File → 📅 Schedule for Later\\.`
    : pending.map((p, i) => `${i + 1}\\. *${format.escapeMd(p.file_name)}* → ${format.escapeMd(p.repo_name)} — ${format.escapeMd(timezone.formatInZone(new Date(p.scheduled_for), tz, { hour12 }))}`).join('\n');

  const rows = [];
  pending.forEach((p, i) => {
    rows.push([
      style.callback(`▶️ ${i + 1}. Run Now`, `scheduploads:runnow:${p.id}`),
      style.callback('✏️ Edit', `scheduploads:edit:${p.id}`),
    ]);
    rows.push([style.callback('❌ Cancel', `scheduploads:cancel:${p.id}`)]);
  });
  rows.push([style.callback('⬅️ Back', 'automation:schedulehub', style.BLUE)]);

  await ephemeral.sendEphemeral(ctx, '📤 Scheduled Uploads', bbtb.automationScheduleSub);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function cancelScheduled(ctx, id) {
  await scheduledUploads.cancel(ctx.from.id, Number(id));
  await ctx.reply('❌ Scheduled upload cancelled — nothing will be committed.');
  return showScheduledUploads(ctx);
}

/** ▶️ Run Now — commits immediately instead of waiting for the scheduled
 * time. Re-downloads the file from Telegram via its stored file_id, same
 * as the background poller does — kept as its own small copy rather than
 * sharing code across those two very different execution contexts (one
 * has a live chat to reply into and requireConnected, the other only has
 * bot.telegram.sendMessage), same reasoning as Scheduled Repos' own
 * runScheduledNow. */
async function runScheduledNow(ctx, id) {
  const item = await scheduledUploads.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled upload is no longer pending.');
    return showScheduledUploads(ctx);
  }

  const token = await requireConnected(ctx);
  if (!token) return;

  const github = require('../lib/github');
  const repoCache = require('../lib/repoCache');
  const activity = require('../lib/activity');

  await ctx.reply(`▶️ Uploading "${format.escapeMd(item.file_name)}" now\\.\\.\\.`, { parse_mode: 'MarkdownV2' });
  try {
    const fileLink = await ctx.telegram.getFileLink(item.file_id);
    const res = await fetch(fileLink.href, { signal: AbortSignal.timeout(20000) });
    const buffer = Buffer.from(await res.arrayBuffer());

    const user = await repoCache.getUser(ctx.from.id, token);
    await github.commitMultipleFiles(
      token,
      user.login,
      item.repo_name,
      [{ path: item.target_path || item.file_name, content: buffer }],
      item.commit_message || 'Update via GitroHub',
      []
    );
    repoCache.invalidateRepos(ctx.from.id);
    repoCache.invalidateLanguages(ctx.from.id, item.repo_name);
    repoCache.invalidateTreeStats(ctx.from.id, item.repo_name);

    await scheduledUploads.markCompleted(item.id);
    await activity.log(ctx.from.id, '📤', `Scheduled upload committed now → ${item.repo_name}`, { detail: item.target_path || item.file_name });
    await ctx.reply(`✅ Uploaded to ${item.repo_name}`, bbtb.automationScheduleSub);
  } catch (err) {
    await scheduledUploads.markFailed(item.id, err.message);
    await ctx.reply(format.errorMessage(`Couldn\u2019t upload "${item.file_name}" now`, err.message, 'Try again, or edit it first.'));
  }
  return showScheduledUploads(ctx);
}

/** ✏️ Edit — target path, commit message, or time. No file-swap yet —
 * cancel and re-schedule if the wrong file was picked. */
async function showEditMenu(ctx, id) {
  const item = await scheduledUploads.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled upload is no longer pending.');
    return showScheduledUploads(ctx);
  }
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';
  const hour12 = user.time_format === '12h';

  const text =
    `✏️ *Edit Scheduled Upload*\n\n` +
    `📦 Repo: ${format.escapeMd(item.repo_name)}\n` +
    `📁 File: ${format.escapeMd(item.file_name)}\n` +
    `📍 Path: ${format.escapeMd(item.target_path || item.file_name)}\n` +
    `📝 Commit message: ${item.commit_message ? format.escapeMd(item.commit_message) : '_Default_'}\n` +
    `⏰ Time: ${format.escapeMd(timezone.formatInZone(new Date(item.scheduled_for), tz, { hour12 }))}`;

  const rows = [
    [style.callback('📍 Path', `scheduploads:editpath:${id}`), style.callback('📝 Commit Message', `scheduploads:editmsg:${id}`)],
    [style.callback('⏰ Time', `scheduploads:edittime:${id}`, style.BLUE)],
    [style.callback('▶️ Run Now', `scheduploads:runnow:${id}`)],
    [style.callback('⬅️ Back', 'scheduploads:back', style.BLUE)],
  ];
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function showTimeMenu(ctx, id) {
  await ctx.reply('⏰ When should this be uploaded instead?', Markup.inlineKeyboard([
    [style.callback('In 1 hour', `scheduploads:settime:${id}:1h`)],
    [style.callback('In 3 days', `scheduploads:settime:${id}:3days`)],
    [style.callback('Tomorrow 9am', `scheduploads:settime:${id}:tomorrow9am`)],
    [style.callback('⌨️ Custom', `scheduploads:settime:${id}:custom`)],
  ]));
}

async function setQuickTime(ctx, id, pick) {
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';

  if (pick === 'custom') {
    ctx.session.editingUploadTime = { id };
    await ephemeral.sendEphemeral(
      ctx,
      `⌨️ Send a time in your timezone (${tz}) — just "14:00" works (today, or tomorrow if that's already passed), or add a date: "12-25 09:00", or the full "2026-09-15 14:00" if you want to be exact. 12-hour like "2:30pm" also works.`,
      bbtb.cancelOnly
    );
    return;
  }

  const now = new Date();
  let scheduledFor;
  if (pick === '1h') scheduledFor = new Date(now.getTime() + 60 * 60 * 1000);
  else if (pick === '3days') scheduledFor = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);
  else if (pick === 'tomorrow9am') {
    const todayLocal = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
    const [ty, tm, td] = todayLocal.split('-').map(Number);
    const tomorrowLocal = new Date(Date.UTC(ty, tm - 1, td + 1));
    const y = tomorrowLocal.getUTCFullYear();
    const mo = String(tomorrowLocal.getUTCMonth() + 1).padStart(2, '0');
    const d = String(tomorrowLocal.getUTCDate()).padStart(2, '0');
    scheduledFor = timezone.zonedTimeToUtc(`${y}-${mo}-${d}`, '09:00', tz);
    if (scheduledFor.getTime() <= now.getTime()) scheduledFor = new Date(scheduledFor.getTime() + 24 * 60 * 60 * 1000);
  }

  return finalizeTimeEdit(ctx, id, scheduledFor);
}

async function handleCustomTimeInput(ctx) {
  const state = ctx.session.editingUploadTime;
  delete ctx.session.editingUploadTime;
  if (!state) return;

  if (ctx.message.text === '❌ Cancel') {
    await ctx.reply('Cancelled.');
    return showEditMenu(ctx, state.id);
  }

  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';

  const scheduledFor = timezone.parseFlexibleDateTime(ctx.message.text.trim(), tz);
  if (!scheduledFor) {
    await ctx.reply(format.errorMessage('Couldn\u2019t read that', 'try "14:00", "12-25 09:00", or "2026-09-15 14:00"', '12-hour like "2:30pm" also works, or ❌ Cancel.'));
    ctx.session.editingUploadTime = state;
    return;
  }
  if (scheduledFor.getTime() <= Date.now()) {
    await ctx.reply(format.errorMessage('That time has already passed', `that resolves to the past in ${tz}`, 'Send a future date/time, or ❌ Cancel.'));
    ctx.session.editingUploadTime = state;
    return;
  }

  return finalizeTimeEdit(ctx, state.id, scheduledFor);
}

async function finalizeTimeEdit(ctx, id, scheduledFor) {
  const item = await scheduledUploads.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled upload is no longer pending.');
    return showScheduledUploads(ctx);
  }
  await scheduledUploads.updateField(ctx.from.id, Number(id), 'scheduledFor', scheduledFor);
  await ephemeral.sendEphemeral(ctx, '✅ Time updated.');
  return showEditMenu(ctx, id);
}

/** Text-input flows for editing path/commit message, driven by
 * ctx.session.editingUploadField (see bot.js text router). */
async function startEditPath(ctx, id) {
  ctx.session.editingUploadField = { id, field: 'targetPath' };
  await ephemeral.sendEphemeral(ctx, '📍 Send the new path (including filename) this should be committed to, e.g. "docs/notes.md".', bbtb.cancelOnly);
}

async function startEditMessage(ctx, id) {
  ctx.session.editingUploadField = { id, field: 'commitMessage' };
  await ephemeral.sendEphemeral(ctx, '📝 Send the new commit message (or "default" to use your default commit message).', bbtb.cancelOnly);
}

async function handleFieldTextInput(ctx) {
  const state = ctx.session.editingUploadField;
  delete ctx.session.editingUploadField;
  if (!state) return;

  if (ctx.message.text === '❌ Cancel') {
    await ctx.reply('Cancelled.');
    return showEditMenu(ctx, state.id);
  }

  const text = ctx.message.text.trim();
  if (state.field === 'targetPath') {
    await scheduledUploads.updateField(ctx.from.id, Number(state.id), 'targetPath', text);
  } else if (state.field === 'commitMessage') {
    const msg = text.toLowerCase() === 'default' ? null : text;
    await scheduledUploads.updateField(ctx.from.id, Number(state.id), 'commitMessage', msg);
  }

  await ephemeral.sendEphemeral(ctx, '✅ Updated.');
  return showEditMenu(ctx, state.id);
}

module.exports = {
  showScheduledUploads,
  cancelScheduled,
  runScheduledNow,
  showEditMenu,
  showTimeMenu,
  setQuickTime,
  handleCustomTimeInput,
  startEditPath,
  startEditMessage,
  handleFieldTextInput,
};
