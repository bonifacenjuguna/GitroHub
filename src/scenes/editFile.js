const { Scenes, Markup } = require('telegraf');
const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');

const scene = new Scenes.WizardScene(
  'editFile',

  async (ctx) => {
    const { repoName, filePath } = ctx.scene.state;
    ctx.wizard.state.repoName = repoName;
    ctx.wizard.state.filePath = filePath;

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    try {
      const user = await github.getAuthenticatedUser(token);
      const { content, sha } = await github.getFileContent(token, user.login, repoName, filePath);
      ctx.wizard.state.originalContent = content;
      ctx.wizard.state.sha = sha;

      await ctx.reply(
        `✏️ Editing ${filePath}\nCurrent content sent below. Reply with the full new content to replace it, or Cancel.`,
        bbtb.cancelOnly
      );
      // Send current content as its own message/document so it doesn't get lost in the prompt
      if (content.length < 3500) {
        const format = require('../lib/format');
        await ctx.reply('```\n' + format.escapeCodeBlock(content) + '\n```', { parse_mode: 'MarkdownV2' }).catch(() =>
          ctx.replyWithDocument({ source: Buffer.from(content), filename: filePath.split('/').pop() })
        );
      } else {
        await ctx.replyWithDocument({ source: Buffer.from(content), filename: filePath.split('/').pop() });
      }
      return ctx.wizard.next();
    } catch (err) {
      await ctx.reply(format.errorMessage('Couldn\u2019t load file for editing', err.message, 'Try again.'), bbtb.mainMenu);
      return ctx.scene.leave();
    }
  },

  async (ctx) => {
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      await ctx.reply('Edit cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (!ctx.message || !ctx.message.text) {
      await ctx.reply('Reply with the new file content as text, or ❌ Cancel.');
      return;
    }

    ctx.wizard.state.newContent = ctx.message.text;
    const oldLines = ctx.wizard.state.originalContent.split('\n').length;
    const newLines = ctx.message.text.split('\n').length;
    const diff = newLines - oldLines;
    const diffLabel = diff >= 0 ? `+${diff} lines added` : `${Math.abs(diff)} lines removed`;

    await ctx.reply(
      `✏️ Confirm edit to ${ctx.wizard.state.filePath}\n${diffLabel}`,
      Markup.inlineKeyboard([
        [Markup.button.callback('✅ Commit Change', 'edit:confirm')],
        [Markup.button.callback('❌ Cancel', 'edit:cancel')],
      ])
    );
    return ctx.wizard.next();
  },

  async (ctx) => {
    if (!ctx.callbackQuery) {
      await ctx.reply('Tap ✅ Commit Change or ❌ Cancel above.');
      return;
    }
    await ctx.answerCbQuery();
    if (ctx.callbackQuery.data === 'edit:cancel') {
      await ctx.reply('Edit cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const { repoName, filePath, newContent, sha } = ctx.wizard.state;
    try {
      const user = await github.getAuthenticatedUser(token);
      // Re-fetch current sha to detect if file changed since we opened it
      const current = await github.getFileContent(token, user.login, repoName, filePath);
      if (current.sha !== sha) {
        await ctx.reply(format.errorMessage(
          'Edit failed',
          `${filePath} was modified on GitHub since you opened it`,
          'Your changes weren\u2019t lost — view the latest version first to avoid overwriting it.'
        ), bbtb.mainMenu);
        return ctx.scene.leave();
      }

      await github.putFile(token, user.login, repoName, filePath, newContent, `Update ${filePath} via GitroHub`, sha);
      await activity.log(ctx.from.id, '✏️', `Edited file → ${filePath} (${repoName})`);
      await ctx.reply(format.successMessage(`Updated ${filePath}`), bbtb.mainMenu);
    } catch (err) {
      await activity.log(ctx.from.id, '⚠️', `Edit failed → ${filePath}`, { detail: err.message, isError: true });
      await ctx.reply(format.errorMessage('Edit failed', err.message, 'Try again.'), bbtb.mainMenu);
    }
    return ctx.scene.leave();
  }
);

module.exports = scene;
