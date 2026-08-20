const { Scenes, Markup } = require('telegraf');
const github = require('../lib/github');
const repoCache = require('../lib/repoCache');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');

const scene = new Scenes.WizardScene(
  'renameRepo',

  async (ctx) => {
    ctx.wizard.state.oldName = ctx.wizard.state.oldName || ctx.scene.state.repoName;
    await ctx.reply(
      `✏️ Current name: ${ctx.wizard.state.oldName}\nSend the new repo name.`,
      bbtb.cancelOnly
    );
    return ctx.wizard.next();
  },

  async (ctx) => {
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      await ctx.reply('Rename cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (!ctx.message || !ctx.message.text) {
      await ctx.reply('Send the new name as text, or ❌ Cancel.');
      return;
    }
    const newName = ctx.message.text.trim();
    if (!/^[a-zA-Z0-9._-]+$/.test(newName)) {
      await ctx.reply(format.errorMessage('Invalid repo name', `"${newName}" contains disallowed characters`, 'Use only letters, numbers, dots, hyphens, underscores.'));
      return;
    }
    ctx.wizard.state.newName = newName;

    const keyboard = Markup.inlineKeyboard([
      [Markup.button.callback('✅ Confirm Rename', 'rename:confirm')],
      [Markup.button.callback('❌ Cancel', 'rename:cancel')],
    ]);

    await ctx.reply(
      `✏️ Rename repository?\n\n${ctx.wizard.state.oldName} → ${newName}\n\n` +
      `⚠️ Old links/clones using the previous name will redirect automatically (GitHub handles this), but local git remotes you've set up elsewhere won't update on their own.`,
      keyboard
    );
    return ctx.wizard.next();
  },

  async (ctx) => {
    if (!ctx.callbackQuery) {
      await ctx.reply('Tap ✅ Confirm Rename or ❌ Cancel above.');
      return;
    }
    await ctx.answerCbQuery();

    if (ctx.callbackQuery.data === 'rename:cancel') {
      await ctx.reply('Rename cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (ctx.callbackQuery.data !== 'rename:confirm') {
      // Stray/stale callback from an unrelated old message — don't treat
      // it as a rename confirmation.
      await ctx.reply('Tap ✅ Confirm Rename or ❌ Cancel above.');
      return;
    }

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const { oldName, newName } = ctx.wizard.state;
    try {
      const user = await repoCache.getUser(ctx.from.id, token);
      const repo = await github.renameRepo(token, user.login, oldName, newName);
      // v0.8.2 #1 — this used to re-`require('../lib/repoCache')` into a
      // local const right here, which shadowed the module-level `repoCache`
      // import for this entire block (const/let are hoisted to the top of
      // their block, just left uninitialized). That made the EARLIER
      // `repoCache.getUser(...)` call above reference the local binding
      // before it was assigned — "Cannot access 'repoCache' before
      // initialization", on every single rename. Now just reuses the
      // already-imported module-level `repoCache`.
      repoCache.invalidateRepos(ctx.from.id);
      repoCache.invalidateLanguages(ctx.from.id, oldName);
      // Also drop any stale tree/size cache entry under the OLD name — it's
      // now orphaned (nothing will ever look it up again under that name),
      // but leaving it around for its 60s TTL was an inconsistency versus
      // every other repo-mutating path, which invalidates all three caches
      // together (see repoView.js executeDeleteRepo, browseFiles.js
      // executeDeleteFile, editFile.js, uploadFile.js commit step).
      repoCache.invalidateTreeStats(ctx.from.id, oldName);
      await activity.log(ctx.from.id, '✏️', `Renamed → ${oldName} → ${newName}`);
      await ctx.reply(`✅ Renamed: ${oldName} → ${repo.name}\n🔗 ${repo.html_url}`, bbtb.mainMenu);
    } catch (err) {
      await activity.log(ctx.from.id, '⚠️', `Rename failed → ${oldName}`, { detail: err.message, isError: true });
      const errorHelpers = require('../lib/errorHelpers');
      if (errorHelpers.isAuthError(err)) {
        await errorHelpers.replyGithubError(ctx, err, 'Rename failed');
      } else {
        const reason = err.status === 422
          ? `"${newName}" is already taken by another repo on your account`
          : err.message;
        await ctx.reply(format.errorMessage('Rename failed', reason, 'Choose a different name.'), bbtb.mainMenu);
      }
    }
    return ctx.scene.leave();
  }
);

module.exports = scene;
