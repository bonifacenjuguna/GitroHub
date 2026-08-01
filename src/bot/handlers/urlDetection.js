'use strict';

const { InlineKeyboard } = require('grammy');
const reposApi = require('../../github/repos');
const { formatError } = require('../../utils/errors');

const GITHUB_URL_RE = /github\.com\/([\w.-]+)\/([\w.-]+)(\/tree\/([\w./-]+))?/i;

function registerUrlDetection(bot) {
  bot.on('message:text', async (ctx) => {
    const match = ctx.message.text.match(GITHUB_URL_RE);
    if (!match) return; // not a GitHub URL — nothing else claimed this message, just ignore

    const [, owner, repoRaw] = match;
    const repoName = repoRaw.replace(/\.git$/, '');
    const branch = match[4];

    try {
      const repo = await reposApi.getRepo(ctx.from.id, owner, repoName);
      let body = `🔗 Detected: ${repo.full_name}\n\n⭐ ${repo.stargazers_count} · 🍴 ${repo.forks_count}`;
      if (repo.language) body += ` · ${repo.language}`;
      if (repo.description) body += `\n"${repo.description}"`;

      const kb = new InlineKeyboard()
        .text('⬇️ Download ZIP', `repo:${encodeURIComponent(repo.full_name)}:download`)
        .text('🍴 Fork This', `repo:${encodeURIComponent(repo.full_name)}:fork`).row()
        .text('👁️ Preview', `repo:open:${encodeURIComponent(repo.full_name)}`)
        .text('❌ Cancel', 'flow:cancel');

      await ctx.reply(body, { reply_markup: kb });
    } catch (err) {
      if (err.status === 404) {
        return ctx.reply('🔒 That repository could not be found, or is private and you don\'t have access to it with your connected account.');
      }
      const formatted = formatError(err, {});
      await ctx.reply(formatted.text);
    }
  });
}

module.exports = { registerUrlDetection };
