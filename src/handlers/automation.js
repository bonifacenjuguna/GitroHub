const { Markup } = require('telegraf');
const style = require('../keyboards/buttonStyle');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const format = require('../lib/format');
const config = require('../config');
const requireConnected = require('../lib/requireConnected');
const tags = require('../lib/tags');
const activity = require('../lib/activity');

/**
 * 🤖 Automation — the parent hub for everything that acts on repos without
 * a person tapping through it manually: Defaults (starting values), Auto-Tag
 * Rules (background tagging by condition), and the Automation Log (an audit
 * trail of what ran on its own, separate from the person's own actions).
 *
 * Defaults itself is untouched — same handler, same data, same behavior —
 * just relocated one level deeper (myDefaults.showDefaults, entered via
 * 'automation:defaults' instead of its own BBTB button).
 */
async function showAutomationHub(ctx, { skipBbtb = false } = {}) {
  const users = require('../lib/users');
  const connected = await users.isConnected(ctx.from.id);
  if (!connected) return;

  const text =
    `🤖 *Automation*\n\n` +
    `Rules and background behavior that act on your repos without a manual tap every time\\.\n\n` +
    `▸ ⚙️ *Defaults* — starting values for new repos, uploads, sort/filter, notifications\\.\n` +
    `▸ 🏷️ *Auto\\-Tag* — automatically tag repos that match a condition \\(language, name pattern, visibility\\)\\.\n` +
    `▸ 📜 *Log* — what ran on its own, kept separate from things you did yourself\\.`;

  if (!skipBbtb) await ctx.reply('🤖 Automation', bbtb.backToSettings);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...inline.automationHub() });
}

// ─── Auto-Tag Rules ────────────────────────────────────────────────

function parseRule(t) {
  if (!t.auto_rule_json) return null;
  try { return JSON.parse(t.auto_rule_json); } catch (_) { return null; }
}

async function showAutoTagRules(ctx) {
  const userTags = await tags.listTags(ctx.from.id);

  let text = `🏷️ *Auto\\-Tag Rules*\n\nAttach a condition to a tag and GitroHub will offer to apply it automatically whenever it matches\\. ⚡ \\= rule active, ➖ \\= none\\.\n\n`;
  if (userTags.length === 0) {
    text += `You don\u2019t have any tags yet\\. Create one first from a repo\u2019s 🏷️ Tags menu, then come back here to attach a rule to it\\.`;
  } else {
    text += userTags
      .map((t) => `${t.auto_rule_json ? '⚡' : '➖'} ${t.emoji} *${format.escapeMd(t.name)}* — ${format.escapeMd(tags.describeRule(parseRule(t)))}`)
      .join('\n');
  }

  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...inline.autoTagRulesMenu(userTags) });
}

async function startEditRule(ctx, tagId) {
  const userTags = await tags.listTags(ctx.from.id);
  const tag = userTags.find((t) => String(t.id) === String(tagId));
  if (!tag) {
    await ctx.reply('That tag no longer exists.');
    return showAutoTagRules(ctx);
  }
  const rule = parseRule(tag);
  await ctx.reply(
    `${tag.emoji} *${format.escapeMd(tag.name)}*\nCurrent rule: ${format.escapeMd(tags.describeRule(rule))}\n\nWhat should trigger this tag automatically?`,
    { parse_mode: 'MarkdownV2', ...inline.ruleFieldMenu(tagId, !!rule) }
  );
}

async function selectRuleField(ctx, tagId, field) {
  if (field === 'visibility') {
    await ctx.reply('Choose the visibility that should trigger this tag:', inline.ruleVisibilityMenu(tagId));
    return;
  }
  ctx.session.automationRuleInput = { tagId, field };
  const prompt = field === 'language'
    ? '💻 Type the exact language name as GitHub reports it (e.g. Python, JavaScript, TypeScript).'
    : '📛 Type a name pattern, using * as a wildcard (e.g. api-*, *-service).';
  await ctx.reply(prompt, bbtb.cancelOnly);
}

async function setVisibilityRule(ctx, tagId, value) {
  await tags.setAutoRule(ctx.from.id, Number(tagId), { field: 'visibility', op: 'eq', value });
  await ctx.reply(format.successMessage('Rule saved'));
  return showAutoTagRules(ctx);
}

/** Called from the text router (bot.js) when ctx.session.automationRuleInput is set */
async function handleRuleValueInput(ctx, text) {
  const state = ctx.session.automationRuleInput;
  delete ctx.session.automationRuleInput;
  if (!state) return;

  if (text === '❌ Cancel') {
    await ctx.reply('Cancelled.');
    return showAutoTagRules(ctx);
  }

  const value = text.trim();
  if (!value) {
    await ctx.reply('Send a value as text, or ❌ Cancel.');
    ctx.session.automationRuleInput = state; // let them retry without losing the field they picked
    return;
  }

  const rule = state.field === 'name'
    ? { field: 'name', op: 'matches', value }
    : { field: 'language', op: 'eq', value };
  await tags.setAutoRule(ctx.from.id, Number(state.tagId), rule);
  await ctx.reply(format.successMessage('Rule saved'));
  return showAutoTagRules(ctx);
}

async function clearRule(ctx, tagId) {
  await tags.setAutoRule(ctx.from.id, Number(tagId), null);
  await ctx.reply('➖ Rule cleared.');
  return showAutoTagRules(ctx);
}

/** Applies every active rule against every repo, retroactively — separate
 * from the per-repo suggestion on Repo View (which only checks the one
 * repo you're looking at, as it's opened). Locked like every other
 * multi-repo write in the bot (see Bulk Actions) since it fans out across
 * the whole account in one tap. */
async function runRulesNow(ctx) {
  const actionLock = require('../lib/actionLock');
  const { skipped } = await actionLock.withLock(ctx.from.id, 'runAutoRules', () => _runRulesNow(ctx));
  if (skipped) await ctx.reply('⏳ Already running — please wait a moment.');
}

async function _runRulesNow(ctx) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const repoCache = require('../lib/repoCache');
  const allRepos = await repoCache.getRepos(ctx.from.id, token);
  const existingByRepo = await tags.tagsForRepos(ctx.from.id, allRepos.map((r) => r.name));

  let tagsApplied = 0;
  let reposAffected = 0;
  await ctx.reply(`▶️ Checking ${allRepos.length} repo(s) against your auto-tag rules...`);

  for (const repo of allRepos) {
    const matches = await tags.evaluateAutoRules(ctx.from.id, repo);
    if (matches.length === 0) continue;
    const already = new Set((existingByRepo[repo.name] || []).map((t) => t.id));
    const newMatches = matches.filter((m) => !already.has(m.id));
    if (newMatches.length === 0) continue;
    for (const m of newMatches) {
      await tags.assignTag(ctx.from.id, repo.name, m.id);
      tagsApplied++;
    }
    reposAffected++;
  }

  await activity.log(
    ctx.from.id,
    '🤖',
    `Auto-tag rules run → ${tagsApplied} tag(s) applied across ${reposAffected} repo(s)`,
    { isAutomated: true }
  );

  await ctx.reply(
    tagsApplied > 0
      ? `✅ Applied ${tagsApplied} tag(s) across ${reposAffected} repo(s).`
      : '➖ No new matches — everything\u2019s already tagged correctly.'
  );
  return showAutoTagRules(ctx);
}

/** One-tap accept for the suggestion shown inline on Repo View when an
 * active rule matches a repo that doesn't have that tag yet. */
async function applySuggestedTag(ctx, repoName, tagId) {
  const userTags = await tags.listTags(ctx.from.id);
  const tag = userTags.find((t) => String(t.id) === String(tagId));
  await tags.assignTag(ctx.from.id, repoName, Number(tagId));
  await activity.log(
    ctx.from.id,
    '🏷️',
    `Auto-tag suggestion applied → ${tag ? tag.name : `tag #${tagId}`} (${repoName})`,
    { isAutomated: true }
  );
  try {
    await ctx.editMessageText(`✅ Tagged ${repoName}${tag ? ` with ${tag.emoji} ${tag.name}` : ''}.`);
  } catch (_) {
    await ctx.reply(`✅ Tagged ${repoName}.`);
  }
}

async function dismissSuggestion(ctx) {
  try {
    await ctx.editMessageText('➖ Dismissed.');
  } catch (_) { /* message too old to edit — non-fatal, it's just a suggestion */ }
}

// ─── Automation Log ────────────────────────────────────────────────

async function showAutomationLog(ctx, { page = 1, edit = false } = {}) {
  const telegramId = ctx.from.id;
  const limit = config.ACTIVITY_PER_PAGE;
  const offset = (page - 1) * limit;

  const { rows, total } = await activity.recent(telegramId, { limit, offset, automatedOnly: true });
  const totalPages = Math.max(1, Math.ceil(total / limit));

  let text = `📜 *Automation Log*\n\nWhat GitroHub did on its own \\(auto\\-tag rules, applied suggestions\\) — separate from your own taps\\.\n\n`;
  if (rows.length === 0) {
    text += 'Nothing automated has run yet\\.';
  } else {
    text += rows
      .map((r) => `🕐 ${format.escapeMd(format.relativeTime(r.created_at))}   ${r.icon} ${format.escapeMd(r.summary)}`)
      .join('\n');
    text += `\n\nShowing last ${rows.length} of ${total} event${total === 1 ? '' : 's'}`;
  }

  const keyboard = inline.automationLogPagination(page, totalPages);
  if (edit) {
    await ctx.editMessageText(text, { parse_mode: 'MarkdownV2', ...keyboard });
  } else {
    await ctx.reply(text, { parse_mode: 'MarkdownV2', ...keyboard });
  }
}

module.exports = {
  showAutomationHub,
  showAutoTagRules,
  startEditRule,
  selectRuleField,
  setVisibilityRule,
  handleRuleValueInput,
  clearRule,
  runRulesNow,
  applySuggestedTag,
  dismissSuggestion,
  showAutomationLog,
};
