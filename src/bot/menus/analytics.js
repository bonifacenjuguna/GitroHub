'use strict';

const { InlineKeyboard } = require('grammy');
const { getClient } = require('../../github/client');

function enc(s) { return encodeURIComponent(s); }

function registerAnalytics(bot) {
  bot.callbackQuery('menu:analytics_hub', async (ctx) => {
    const kb = new InlineKeyboard().text('📦 Pick a Repo', 'menu:repos').row().text('⬅️ Back to Menu', 'menu:main');
    await ctx.editOrReply('📊 Analytics\n\nOpen a repository, then tap 📊 Insights for commit activity, contributors, traffic, and stars/forks trends.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):insights$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const kb = new InlineKeyboard()
      .text('📈 Commit Activity', `insights:${enc(fullName)}:commits`).text('👥 Contributors', `insights:${enc(fullName)}:contributors`).row()
      .text('🚦 Traffic', `insights:${enc(fullName)}:traffic`).row()
      .text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);
    await ctx.editOrReply(`📊 Analytics — ${fullName}`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^insights:(.+):contributors$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repo] = fullName.split('/');
    const octokit = await getClient(ctx.from.id);
    const { data } = await octokit.rest.repos.listContributors({ owner, repo, per_page: 10 });
    let body = `👥 Contributors (${data.length})\n\n`;
    data.forEach((c) => (body += `${c.login}   ${c.contributions} commits\n`));
    await ctx.editOrReply(body, { reply_markup: new InlineKeyboard().text('⬅️ Back', `repo:${enc(fullName)}:insights`) });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^insights:(.+):traffic$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repo] = fullName.split('/');
    try {
      const octokit = await getClient(ctx.from.id);
      const [views, clones] = await Promise.all([
        octokit.rest.repos.getViews({ owner, repo }),
        octokit.rest.repos.getClones({ owner, repo }),
      ]);
      const body = `🚦 Traffic — Last 14 days\n\n👁️ Views: ${views.data.count} (${views.data.uniques} unique)\n📥 Clones: ${clones.data.count} (${clones.data.uniques} unique)`;
      await ctx.editOrReply(body, { reply_markup: new InlineKeyboard().text('⬅️ Back', `repo:${enc(fullName)}:insights`) });
    } catch (err) {
      await ctx.editOrReply('🚦 Traffic data requires push access to this repository.', { reply_markup: new InlineKeyboard().text('⬅️ Back', `repo:${enc(fullName)}:insights`) });
    }
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^insights:(.+):commits$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repo] = fullName.split('/');
    const octokit = await getClient(ctx.from.id);
    const { data } = await octokit.rest.repos.getCommitActivityStats({ owner, repo });
    const totalLast4Weeks = Array.isArray(data) ? data.slice(-4).reduce((sum, w) => sum + w.total, 0) : 0;
    await ctx.editOrReply(`📈 Commit Activity\n\n${totalLast4Weeks} commits in the last 4 weeks.`, { reply_markup: new InlineKeyboard().text('⬅️ Back', `repo:${enc(fullName)}:insights`) });
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerAnalytics };
