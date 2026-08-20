const { Scenes, Markup } = require('telegraf');
const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const confirmFlow = require('../lib/confirmFlow');

const LICENSE_LABELS = { mit: 'MIT', 'apache-2.0': 'Apache 2.0', 'gpl-3.0': 'GPL v3', 'bsd-3-clause': 'BSD' };

// v0.8.2 #8 — was a hand-duplicated copy of keyboards/inline.js's exported
// `cancelConfirm(scenePrefix)` factory (same labels, same callback shape).
// Now reuses the one source of truth instead of maintaining two.
const cancelConfirmKeyboard = inline.cancelConfirm('createrepo');

// ─── Step re-render helpers ──────────────────────────────────────────
// v0.8.2 #7 — ⬅️ Back previously just moved the wizard cursor and said
// "Going back..." with no new prompt (see the old comment this replaced:
// "Telegraf wizard doesn't auto re-render"). That's harmless for the two
// TEXT-input steps (name, description) since their handlers just process
// whatever the person sends next — but for the three CALLBACK-driven steps
// (visibility, README, license) it left the person stuck with no live
// buttons to tap, needing to scroll up and find the old (still technically
// clickable) message. These helpers re-render the actual prompt+buttons for
// a target step, called both from the normal forward flow and from Back —
// matching the pattern uploadFile.js's scene already used correctly.

async function renderVisibilityPrompt(ctx) {
  const defaultsLib = require('../lib/defaults');
  const d = await defaultsLib.getDefaults(ctx.from.id);
  const defaultVis = d ? d.default_visibility : 'private';
  const keyboard = Markup.inlineKeyboard([
    [Markup.button.callback(defaultVis === 'private' ? '🔒 Private ✓ default' : '🔒 Private', 'create:visibility:private')],
    [Markup.button.callback(defaultVis === 'public' ? '🌐 Public ✓ default' : '🌐 Public', 'create:visibility:public')],
  ]);
  await ctx.reply(`Repo name: ${ctx.wizard.state.data.name} ✅\nChoose visibility:`, keyboard);
}

async function renderReadmePrompt(ctx) {
  await ctx.reply(
    '📄 Include a default README.md?',
    Markup.inlineKeyboard([
      [Markup.button.callback('✅ Yes', 'create:readme:yes')],
      [Markup.button.callback('⏭️ Skip', 'create:readme:no')],
    ])
  );
}

async function renderLicensePrompt(ctx) {
  await ctx.reply(
    '⚖️ Choose a license (or skip for none):',
    Markup.inlineKeyboard([
      [Markup.button.callback('MIT', 'create:license:mit')],
      [Markup.button.callback('Apache 2.0', 'create:license:apache-2.0')],
      [Markup.button.callback('GPL v3', 'create:license:gpl-3.0')],
      [Markup.button.callback('BSD', 'create:license:bsd-3-clause')],
      [Markup.button.callback('⏭️ Skip', 'create:license:none')],
    ])
  );
}

async function renderConfirmPrompt(ctx) {
  const { name, isPrivate, description, includeReadme, licenseTemplate } = ctx.wizard.state.data;
  let text = `📦 ${name}\n${isPrivate ? '🔒 Private' : '🌐 Public'}`;
  if (description) text += `\n"${description}"`;
  text += `\n📄 README: ${includeReadme ? 'Yes' : 'Skip'}`;
  text += `\n⚖️ License: ${licenseTemplate ? LICENSE_LABELS[licenseTemplate] : 'None'}`;
  text += '\n\nReady to create this repository?';
  await ctx.reply(text, inline.createRepoConfirm);
}

// Maps a target wizard step index (the step we're going BACK into) to the
// re-render it needs. Steps not listed here (1, 3) are plain text-input
// steps whose handler just processes whatever's sent next — no fresh
// prompt needed, the original one is still visible above.
const STEP_RENDERERS = {
  2: { header: '📦 New Repo — Step 2 of 5', render: renderVisibilityPrompt },
  4: { header: '📦 New Repo — Step 4 of 5', render: renderReadmePrompt },
  5: { header: '📦 New Repo — Step 5 of 5', render: renderLicensePrompt },
  6: { header: '📦 New Repo — Confirm', render: renderConfirmPrompt },
};

const scene = new Scenes.WizardScene(
  'createRepo',

  // Step 0 — ask name
  async (ctx) => {
    ctx.wizard.state.data = {};
    await ctx.reply('📦 Let\u2019s create a new repo.\nSend me the repository name.', bbtb.cancelOnly);
    return ctx.wizard.next();
  },

  // Step 1 — receive name, ask visibility
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;
    if (!ctx.message || !ctx.message.text) {
      await ctx.reply('Send the repository name as text, or ❌ Cancel.');
      return;
    }
    const name = ctx.message.text.trim();
    if (!/^[a-zA-Z0-9._-]+$/.test(name)) {
      await ctx.reply(format.errorMessage(
        'Invalid repo name',
        `"${name}" contains characters GitHub doesn\u2019t allow`,
        'Use only letters, numbers, dots, hyphens, and underscores.'
      ));
      return;
    }
    ctx.wizard.state.data.name = name;
    await ctx.reply('📦 New Repo — Step 2 of 5', bbtb.cancelWithBack);
    await renderVisibilityPrompt(ctx);
    return ctx.wizard.next();
  },

  // Step 2 — receive visibility (via callback), ask description
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;
    if (ctx.callbackQuery && ctx.callbackQuery.data.startsWith('create:visibility:')) {
      const isPrivate = ctx.callbackQuery.data.endsWith('private');
      ctx.wizard.state.data.isPrivate = isPrivate;
      await ctx.answerCbQuery();
      await ctx.reply('Add a short description, or skip.', bbtb.cancelWithSkip);
      return ctx.wizard.next();
    }
    await ctx.reply('Tap 🔒 Private or 🌐 Public above.');
  },

  // Step 3 — receive description (or skip), ask README
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;
    if (ctx.message && ctx.message.text === '⏭️ Skip') {
      ctx.wizard.state.data.description = '';
    } else if (ctx.message && ctx.message.text) {
      ctx.wizard.state.data.description = ctx.message.text.trim();
    } else {
      await ctx.reply('Send a description, tap ⏭️ Skip, or ❌ Cancel.');
      return;
    }

    await ctx.reply('📦 New Repo — Step 4 of 5', bbtb.cancelWithBack);
    await renderReadmePrompt(ctx);
    return ctx.wizard.next();
  },

  // Step 4 — receive README choice, ask license
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;
    if (ctx.callbackQuery && ctx.callbackQuery.data.startsWith('create:readme:')) {
      ctx.wizard.state.data.includeReadme = ctx.callbackQuery.data.endsWith('yes');
      await ctx.answerCbQuery();
      await ctx.reply('📦 New Repo — Step 5 of 5', bbtb.cancelWithBack);
      await renderLicensePrompt(ctx);
      return ctx.wizard.next();
    }
    await ctx.reply('Tap ✅ Yes or ⏭️ Skip above.');
  },

  // Step 5 — receive license choice, show confirm
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;
    if (ctx.callbackQuery && ctx.callbackQuery.data.startsWith('create:license:')) {
      const licenseKey = ctx.callbackQuery.data.split('create:license:')[1];
      ctx.wizard.state.data.licenseTemplate = licenseKey === 'none' ? null : licenseKey;
      await ctx.answerCbQuery();
      await ctx.reply('📦 New Repo — Confirm', bbtb.cancelWithBack);
      await renderConfirmPrompt(ctx);
      return ctx.wizard.next();
    }
    await ctx.reply('Tap a license option above.');
  },

  // Step 6 — confirm and create
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;

    // v0.8.2 #5 — 'create:cancel' (the ❌ Cancel button on THIS confirm
    // screen, from inline.createRepoConfirm) was never handled anywhere.
    // It fell into the generic "wrong input" branch below, which replied
    // "Tap ✅ Create or ❌ Cancel above." — telling the person to do the
    // exact thing they'd just done — and never called answerCbQuery(),
    // leaving Telegram's tap-loading spinner stuck until it timed out.
    // Cancels immediately, matching the equally-simple single-tap pattern
    // renameRepo.js/editFile.js already use for their own inline Cancel
    // buttons (no second "are you sure" — the BBTB ❌ Cancel button already
    // covers that more cautious path via cancelConfirmKeyboard above).
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'create:cancel') {
      await ctx.answerCbQuery();
      await confirmFlow.resolveConfirmation(ctx, 'cancelled', '❌ Repo creation cancelled.');
      await ctx.reply('📍 Main Menu', bbtb.mainMenu);
      return ctx.scene.leave();
    }

    if (!ctx.callbackQuery || ctx.callbackQuery.data !== 'create:confirm') {
      await ctx.reply('Tap ✅ Create or ❌ Cancel above.');
      return;
    }
    await ctx.answerCbQuery();

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const { name, isPrivate, description, includeReadme, licenseTemplate } = ctx.wizard.state.data;
    try {
      const repo = await github.createRepo(token, { name, isPrivate, description, licenseTemplate });
      const repoCache = require('../lib/repoCache');
      repoCache.invalidateRepos(ctx.from.id);

      // auto_init always creates README.md (needed to guarantee a default
      // branch exists for every other feature — Browse Files, Upload, etc.
      // all assume one). If the person chose to skip README, remove that
      // one file right after creation instead of ever creating the repo
      // without a branch.
      if (!includeReadme) {
        try {
          const existing = await github.getFileContent(token, repo.owner.login, repo.name, 'README.md');
          await github.deleteFile(token, repo.owner.login, repo.name, 'README.md', existing.sha, 'Remove default README');
        } catch (_) { /* best-effort — if this fails, an unwanted README is a minor issue, not worth failing repo creation over */ }
      }

      await activity.log(ctx.from.id, '➕', `Created repo → ${name}`, {
        detail: `visibility:${isPrivate ? 'private' : 'public'}`,
      });
      await ctx.reply('📍 Main Menu', bbtb.mainMenu);
      await ctx.reply(
        `✅ Repo created: ${repo.name}\n🔗 ${repo.html_url}`,
        inline.createRepoSuccess(repo.name)
      );

      // "Learn from me" — if your last 3 repos all chose the same visibility
      // and it doesn't match your saved default, offer to update the default.
      const defaults = require('../lib/defaults');
      const suggestion = await defaults.checkVisibilityPattern(ctx.from.id);
      if (suggestion) {
        const label = suggestion === 'private' ? '🔒 Private' : '🌐 Public';
        await ctx.reply(
          `💡 You've chosen ${label} the last 3 times, even though your saved default is different. Update your default to ${label}?`,
          Markup.inlineKeyboard([
            [Markup.button.callback('✅ Yes, Update Default', `createrepo:learndefault:${suggestion}`)],
            [Markup.button.callback('➖ Keep as is', 'createrepo:learndefault:skip')],
          ])
        );
      }
    } catch (err) {
      await activity.log(ctx.from.id, '⚠️', `Create repo failed → ${name}`, { detail: err.message, isError: true });
      const errorHelpers = require('../lib/errorHelpers');
      if (errorHelpers.isAuthError(err)) {
        await errorHelpers.replyGithubError(ctx, err, 'Couldn\u2019t create repo');
      } else {
        const reason = err.status === 422
          ? `GitHub says "${name}" already exists on your account`
          : err.message;
        await ctx.reply(format.errorMessage('Couldn\u2019t create repo', reason, 'Choose a different name and try again.'), bbtb.mainMenu);
      }
    }
    return ctx.scene.leave();
  }
);

/**
 * Shared Back/Cancel handling across every step, per the standing rule:
 * ⬅️ Back steps back one step (data preserved) · ❌ Cancel needs confirming.
 * Returns true if it handled the update (caller should stop processing).
 */
async function handleGlobalActions(ctx) {
  if (ctx.message && ctx.message.text === '❌ Cancel') {
    await ctx.reply('⚠️ Cancel this repo creation? Everything entered so far will be discarded.', cancelConfirmKeyboard);
    return true;
  }
  if (ctx.message && ctx.message.text === '⬅️ Back') {
    const targetStep = Math.max(0, ctx.wizard.cursor - 1);
    ctx.wizard.selectStep(targetStep);
    const renderer = STEP_RENDERERS[targetStep];
    if (renderer) {
      // v0.8.2 #7 — actually re-render the target step's prompt (with live
      // buttons) instead of just announcing "Going back...". This is what
      // makes Back functional again for the button-driven steps.
      await ctx.reply(renderer.header, bbtb.cancelWithBack);
      await renderer.render(ctx);
    } else {
      // Text-input steps (1: name, 3: description) don't need a fresh
      // render — their handler just processes whatever's sent next, and
      // the original prompt is still visible above in the chat.
      await ctx.reply('⬅️ Going back — send your answer for the previous step.');
    }
    return true;
  }
  if (ctx.callbackQuery && ctx.callbackQuery.data === 'createrepo:cancel:confirm') {
    await ctx.answerCbQuery();
    // v0.8.2 #6 — this used to send a brand-new "Repo creation cancelled."
    // message instead of editing the original "Cancel this repo creation?"
    // dialog, leaving its Yes/No buttons live — the exact bug class the
    // v0.8.1 pass fixed everywhere ELSE via confirmFlow.resolveConfirmation.
    // This one flow was missed because it's scene-internal rather than
    // routed through bot.js's callback_query handler. Now consistent with
    // every other confirm/cancel screen in the bot.
    await confirmFlow.resolveConfirmation(ctx, 'confirmed', 'Repo creation cancelled.');
    await ctx.reply('📍 Main Menu', bbtb.mainMenu);
    await ctx.scene.leave();
    return true;
  }
  if (ctx.callbackQuery && ctx.callbackQuery.data === 'createrepo:cancel:abort') {
    await ctx.answerCbQuery();
    await confirmFlow.resolveConfirmation(ctx, 'cancelled', '➖ Continuing where you left off.');
    return true;
  }
  return false;
}

module.exports = scene;
