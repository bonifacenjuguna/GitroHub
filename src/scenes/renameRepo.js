const { Scenes, Markup } = require('telegraf');
const style = require('../keyboards/buttonStyle');
const github = require('../lib/github');
const repoCache = require('../lib/repoCache');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const pins = require('../lib/pins');
const tags = require('../lib/tags');
const pathMemory = require('../lib/pathMemory');

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
      [style.callback('✅ Confirm Rename', 'rename:confirm', style.GREEN)],
      [style.callback('❌ Cancel', 'rename:cancel', style.RED)],
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
    const actionLock = require('../lib/actionLock');
    // Keyed by the repo being renamed, not just 'renameRepo' — renaming
    // one repo must never block an unrelated rename of a different repo
    // (see lib/actionLock.js).
    const { skipped } = await actionLock.withLock(ctx.from.id, `renameRepo:${oldName}`, async () => {
    try {
      const user = await repoCache.getUser(ctx.from.id, token);
      const repo = await github.renameRepo(token, user.login, oldName, newName);
      repoCache.invalidateRepos(ctx.from.id);
      repoCache.invalidateLanguages(ctx.from.id, oldName);
      repoCache.invalidateTreeStats(ctx.from.id, oldName);
      // Root fix — Delete Repo already migrates/cleans up pins, tags, and
      // path-memory (repoView.js's cleanupOrphanedData); Rename had no
      // equivalent, so all three silently pointed at a repo_name that no
      // longer existed anywhere GitHub would ever return it again. Move
      // them to the new name instead of leaving them orphaned.
      await Promise.all([
        pins.renameRepo(ctx.from.id, oldName, newName),
        tags.renameRepo(ctx.from.id, oldName, newName),
        pathMemory.renameRepo(ctx.from.id, oldName, newName),
      ]);
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
    });
    if (skipped) await ctx.reply('⏳ Already renaming — please wait a moment.');
    return ctx.scene.leave();
  }
);

module.exports = scene;
