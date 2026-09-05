const { Markup } = require('telegraf');
const style = require('../keyboards/buttonStyle');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const scheduledRepos = require('../lib/scheduledRepos');
const timezone = require('../lib/timezone');
const requireConnected = require('../lib/requireConnected');
const ephemeral = require('../lib/ephemeral');

const LICENSE_LABELS = { mit: 'MIT', 'apache-2.0': 'Apache 2.0', 'gpl-3.0': 'GPL v3', 'bsd-3-clause': 'BSD' };

/**
 * 📅 Scheduled Commits — the view/manage side of the feature; the actual
 * scheduling happens inline in scenes/createRepo.js's confirm step ("📅
 * Schedule for Later" alongside "✅ Create Now"), and execution happens in
 * index.js's poller. This screen is "what's queued" plus, now, per-item
 * ▶️ Run Now / ✏️ Edit / ❌ Cancel — creating a *new* one always starts
 * from ➕ Create Repo.
 */
async function showScheduledCommits(ctx) {
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';
  const pending = await scheduledRepos.listPending(ctx.from.id);

  let text = `📅 *Scheduled Commits*\n\nRepos queued to be created at a future time — times shown in your timezone \\(${format.escapeMd(tz)}\\)\\.\n\n`;
  text += pending.length === 0
    ? `Nothing scheduled yet\\. Start one from ➕ Create Repo → 📅 Schedule for Later\\.`
    : pending.map((p, i) => `${i + 1}\\. *${format.escapeMd(p.name)}* — ${format.escapeMd(timezone.formatInZone(new Date(p.scheduled_for), tz))}`).join('\n');

  const rows = [];
  pending.forEach((p, i) => {
    rows.push([
      style.callback(`▶️ ${i + 1}. Run Now`, `schedcommits:runnow:${p.id}`),
      style.callback('✏️ Edit', `schedcommits:edit:${p.id}`),
    ]);
    rows.push([style.callback('❌ Cancel', `schedcommits:cancel:${p.id}`)]);
  });
  rows.push([style.callback('⬅️ Back', 'automation:schedulehub', style.BLUE)]);

  await ephemeral.sendEphemeral(ctx, '📅 Scheduled Commits', bbtb.automationScheduleSub);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function cancelScheduled(ctx, id) {
  await scheduledRepos.cancel(ctx.from.id, Number(id));
  await ctx.reply('❌ Scheduled repo cancelled — nothing will be created.');
  return showScheduledCommits(ctx);
}

/** ▶️ Run Now — creates the repo immediately instead of waiting for its
 * scheduled time. Same creation steps as index.js's poller (createRepo,
 * README removal if declined, markCompleted, activity log), just triggered
 * on demand through the interactive ctx instead of the background loop —
 * kept as its own small copy rather than sharing code across those two very
 * different execution contexts (one has a live chat to reply into, the
 * other only has bot.telegram.sendMessage and no requireConnected). */
async function runScheduledNow(ctx, id) {
  const item = await scheduledRepos.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled repo is no longer pending.');
    return showScheduledCommits(ctx);
  }

  const token = await requireConnected(ctx);
  if (!token) return;

  const github = require('../lib/github');
  const repoCache = require('../lib/repoCache');
  const activity = require('../lib/activity');

  await ctx.reply(`▶️ Creating "${format.escapeMd(item.name)}" now\\.\\.\\.`, { parse_mode: 'MarkdownV2' });
  try {
    const repo = await github.createRepo(token, {
      name: item.name,
      isPrivate: item.visibility === 'private',
      description: item.description,
      licenseTemplate: item.license,
    });
    repoCache.invalidateRepos(ctx.from.id);

    if (!item.include_readme) {
      try {
        const existing = await github.getFileContent(token, repo.owner.login, repo.name, 'README.md');
        await github.deleteFile(token, repo.owner.login, repo.name, 'README.md', existing.sha, 'Remove default README');
      } catch (_) { /* best-effort, same as the scheduled poller */ }
    }

    await scheduledRepos.markCompleted(item.id);
    await activity.log(ctx.from.id, '📅', `Scheduled repo created now → ${repo.name}`, { detail: `visibility:${item.visibility}` });
    await ctx.reply(`✅ Created: ${repo.name}\n🔗 ${repo.html_url}`, bbtb.automationScheduleSub);
  } catch (err) {
    const reason = err.status === 422 ? `"${item.name}" already exists on your account` : err.message;
    await ctx.reply(format.errorMessage(`Couldn\u2019t create "${item.name}" now`, reason, 'It stays scheduled — try again, or edit it first.'));
  }
  return showScheduledCommits(ctx);
}

/** ✏️ Edit — a small hub for changing one field of a still-pending
 * scheduled repo before it fires. Editing files/browsing isn't offered
 * here because there's no repo yet to browse — once it's created (on
 * schedule or via ▶️ Run Now), normal Browse Files takes over. */
async function showEditMenu(ctx, id) {
  const item = await scheduledRepos.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled repo is no longer pending.');
    return showScheduledCommits(ctx);
  }
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';

  const text =
    `✏️ *Edit Scheduled Repo*\n\n` +
    `📛 Name: ${format.escapeMd(item.name)}\n` +
    `📝 Description: ${item.description ? format.escapeMd(item.description) : '_None_'}\n` +
    `${format.visibilityLine(item.visibility === 'private')}\n` +
    `⚖️ License: ${item.license ? format.escapeMd(LICENSE_LABELS[item.license] || item.license) : 'None'}\n` +
    `⏰ Time: ${format.escapeMd(timezone.formatInZone(new Date(item.scheduled_for), tz))}`;

  const rows = [
    [style.callback('📛 Name', `schedcommits:editname:${id}`), style.callback('📝 Description', `schedcommits:editdesc:${id}`)],
    [style.callback(item.visibility === 'private' ? '🌐 Make Public' : '🔒 Make Private', `schedcommits:togglevis:${id}`)],
    [style.callback('⚖️ License', `schedcommits:editlicense:${id}`, style.BLUE), style.callback('⏰ Time', `schedcommits:edittime:${id}`, style.BLUE)],
    [style.callback('▶️ Run Now', `schedcommits:runnow:${id}`)],
    [style.callback('⬅️ Back', 'schedcommits:back', style.BLUE)],
  ];
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function toggleVisibility(ctx, id) {
  const item = await scheduledRepos.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled repo is no longer pending.');
    return showScheduledCommits(ctx);
  }
  await scheduledRepos.updateField(ctx.from.id, Number(id), 'visibility', item.visibility === 'private' ? 'public' : 'private');
  return showEditMenu(ctx, id);
}

async function showLicenseMenu(ctx, id) {
  await ctx.reply('⚖️ Choose a license (or skip for none):', Markup.inlineKeyboard([
    [style.callback('MIT', `schedcommits:setlicense:${id}:mit`)],
    [style.callback('Apache 2.0', `schedcommits:setlicense:${id}:apache-2.0`)],
    [style.callback('GPL v3', `schedcommits:setlicense:${id}:gpl-3.0`)],
    [style.callback('BSD', `schedcommits:setlicense:${id}:bsd-3-clause`)],
    [style.callback('⏭️ None', `schedcommits:setlicense:${id}:none`)],
  ]));
}

async function setLicense(ctx, id, licenseKey) {
  await scheduledRepos.updateField(ctx.from.id, Number(id), 'license', licenseKey === 'none' ? null : licenseKey);
  await ephemeral.sendEphemeral(ctx, '✅ License updated.');
  return showEditMenu(ctx, id);
}

async function showTimeMenu(ctx, id) {
  await ctx.reply('⏰ When should this be created instead?', Markup.inlineKeyboard([
    [style.callback('In 1 hour', `schedcommits:settime:${id}:1h`)],
    [style.callback('In 3 days', `schedcommits:settime:${id}:3days`)],
    [style.callback('Tomorrow 9am', `schedcommits:settime:${id}:tomorrow9am`)],
    [style.callback('⌨️ Custom', `schedcommits:settime:${id}:custom`)],
  ]));
}

async function setQuickTime(ctx, id, pick) {
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';

  if (pick === 'custom') {
    ctx.session.editingScheduledTime = { id };
    await ephemeral.sendEphemeral(
      ctx,
      `⌨️ Send the date and time as YYYY-MM-DD HH:MM, in your timezone (${tz}).\nExample: 2026-09-15 14:00`,
      bbtb.cancelOnly
    );
    return;
  }

  const now = new Date();
  let scheduledFor;
  if (pick === '1h') scheduledFor = new Date(now.getTime() + 60 * 60 * 1000);
  else if (pick === '3days') scheduledFor = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);
  else if (pick === 'tomorrow9am') {
    // Same "tomorrow means tomorrow in THEIR calendar" logic as Create
    // Repo's own schedule picker — see scenes/createRepo.js for the
    // date-line reasoning.
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
  const state = ctx.session.editingScheduledTime;
  delete ctx.session.editingScheduledTime;
  if (!state) return;

  if (ctx.message.text === '❌ Cancel') {
    await ctx.reply('Cancelled.');
    return showEditMenu(ctx, state.id);
  }

  const match = ctx.message.text.trim().match(/^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})$/);
  if (!match) {
    await ctx.reply(format.errorMessage('Couldn\u2019t read that', 'expected format is YYYY-MM-DD HH:MM', 'Example: 2026-09-15 14:00'));
    ctx.session.editingScheduledTime = state;
    return;
  }
  const [, dateStr, hh, mm] = match;
  const timeStr = `${hh.padStart(2, '0')}:${mm}`;

  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  const tz = user.timezone || 'UTC';
  const scheduledFor = timezone.zonedTimeToUtc(dateStr, timeStr, tz);
  if (scheduledFor.getTime() <= Date.now()) {
    await ctx.reply(format.errorMessage('That time has already passed', `${dateStr} ${timeStr} (${tz}) is in the past`, 'Send a future date/time, or ❌ Cancel.'));
    ctx.session.editingScheduledTime = state;
    return;
  }

  return finalizeTimeEdit(ctx, state.id, scheduledFor);
}

async function finalizeTimeEdit(ctx, id, scheduledFor) {
  const item = await scheduledRepos.get(ctx.from.id, Number(id));
  if (!item || item.status !== 'pending') {
    await ctx.reply('That scheduled repo is no longer pending.');
    return showScheduledCommits(ctx);
  }
  await scheduledRepos.updateField(ctx.from.id, Number(id), 'scheduledFor', scheduledFor);
  await ephemeral.sendEphemeral(ctx, '✅ Time updated.');
  return showEditMenu(ctx, id);
}

/** Text-input flows for editing name/description, driven by
 * ctx.session.editingScheduledField (see bot.js text router). */
async function startEditName(ctx, id) {
  ctx.session.editingScheduledField = { id, field: 'name' };
  await ephemeral.sendEphemeral(ctx, '📛 Send the new name for this scheduled repo.', bbtb.cancelOnly);
}

async function startEditDescription(ctx, id) {
  ctx.session.editingScheduledField = { id, field: 'description' };
  await ephemeral.sendEphemeral(ctx, '📝 Send the new description (or "none" to clear it).', bbtb.cancelOnly);
}

async function handleFieldTextInput(ctx) {
  const state = ctx.session.editingScheduledField;
  delete ctx.session.editingScheduledField;
  if (!state) return;

  if (ctx.message.text === '❌ Cancel') {
    await ctx.reply('Cancelled.');
    return showEditMenu(ctx, state.id);
  }

  const text = ctx.message.text.trim();
  if (state.field === 'name') {
    if (!/^[a-zA-Z0-9._-]+$/.test(text)) {
      await ctx.reply(format.errorMessage('Invalid repo name', 'GitHub repo names can only contain letters, numbers, dots, hyphens, and underscores', 'Send a valid name, or ❌ Cancel.'));
      ctx.session.editingScheduledField = state;
      return;
    }
    await scheduledRepos.updateField(ctx.from.id, Number(state.id), 'name', text);
  } else if (state.field === 'description') {
    const desc = text.toLowerCase() === 'none' ? null : text;
    await scheduledRepos.updateField(ctx.from.id, Number(state.id), 'description', desc);
  }

  await ephemeral.sendEphemeral(ctx, '✅ Updated.');
  return showEditMenu(ctx, state.id);
}

module.exports = {
  showScheduledCommits,
  cancelScheduled,
  runScheduledNow,
  showEditMenu,
  toggleVisibility,
  showLicenseMenu,
  setLicense,
  showTimeMenu,
  setQuickTime,
  handleCustomTimeInput,
  startEditName,
  startEditDescription,
  handleFieldTextInput,
};
