const { Scenes, Markup } = require('telegraf');
const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');

const cancelConfirmKeyboard = Markup.inlineKeyboard([
  [Markup.button.callback('✅ Yes, Cancel', 'createrepo:cancel:confirm')],
  [Markup.button.callback('⬅️ No, Go Back', 'createrepo:cancel:abort')],
]);

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
    await ctx.reply('📦 New Repo — Step 2 of 4', bbtb.cancelWithBack);

    const defaultsLib = require('../lib/defaults');
    const d = await defaultsLib.getDefaults(ctx.from.id);
    const defaultVis = d ? d.default_visibility : 'private';
    const keyboard = Markup.inlineKeyboard([
      [Markup.button.callback(defaultVis === 'private' ? '🔒 Private ✓ default' : '🔒 Private', 'create:visibility:private')],
      [Markup.button.callback(defaultVis === 'public' ? '🌐 Public ✓ default' : '🌐 Public', 'create:visibility:public')],
    ]);
    await ctx.reply(`Repo name: ${name} ✅\nChoose visibility:`, keyboard);
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

  // Step 3 — receive description (or skip), show confirm
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

    const { name, isPrivate, description } = ctx.wizard.state.data;
    let text = `📦 ${name}\n${isPrivate ? '🔒 Private' : '🌐 Public'}`;
    if (description) text += `\n"${description}"`;
    text += '\n\nReady to create this repository?';

    await ctx.reply('📦 New Repo — Step 4 of 4', bbtb.cancelWithBack);
    await ctx.reply(text, inline.createRepoConfirm);
    return ctx.wizard.next();
  },

  // Step 4 — confirm and create
  async (ctx) => {
    if (await handleGlobalActions(ctx)) return;
    if (!ctx.callbackQuery || ctx.callbackQuery.data !== 'create:confirm') {
      await ctx.reply('Tap ✅ Create or ❌ Cancel above.');
      return;
    }
    await ctx.answerCbQuery();

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const { name, isPrivate, description } = ctx.wizard.state.data;
    try {
      const repo = await github.createRepo(token, { name, isPrivate, description });
      const repoCache = require('../lib/repoCache');
      repoCache.invalidateRepos(ctx.from.id);
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
    ctx.wizard.selectStep(Math.max(0, ctx.wizard.cursor - 1));
    await ctx.reply('⬅️ Going back...');
    // Re-run the previous step's prompt by simulating no-op; simplest is to
    // instruct the user, since Telegraf wizard doesn't auto re-render.
    return true;
  }
  if (ctx.callbackQuery && ctx.callbackQuery.data === 'createrepo:cancel:confirm') {
    await ctx.answerCbQuery();
    await ctx.reply('Repo creation cancelled.', bbtb.mainMenu);
    await ctx.scene.leave();
    return true;
  }
  if (ctx.callbackQuery && ctx.callbackQuery.data === 'createrepo:cancel:abort') {
    await ctx.answerCbQuery();
    await ctx.reply('Continuing where you left off.');
    return true;
  }
  return false;
}

module.exports = scene;
