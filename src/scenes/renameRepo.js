const { Scenes, Markup } = require('telegraf');
const github = require('../lib/github');
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

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const { oldName, newName } = ctx.wizard.state;
    try {
      const user = await github.getAuthenticatedUser(token);
      const repo = await github.renameRepo(token, user.login, oldName, newName);
      await activity.log(ctx.from.id, '✏️', `Renamed → ${oldName} → ${newName}`);
      await ctx.reply(`✅ Renamed: ${oldName} → ${repo.name}\n🔗 ${repo.html_url}`, bbtb.mainMenu);
    } catch (err) {
      const reason = err.status === 422
        ? `"${newName}" is already taken by another repo on your account`
        : err.message;
      await activity.log(ctx.from.id, '⚠️', `Rename failed → ${oldName}`, { detail: err.message, isError: true });
      await ctx.reply(format.errorMessage('Rename failed', reason, 'Choose a different name.'), bbtb.mainMenu);
    }
    return ctx.scene.leave();
  }
);

module.exports = scene;
