'use strict';

const { InlineKeyboard } = require('grammy');
const { query } = require('../../db/postgres/pool');

async function renderAutomationMenu(ctx) {
  const kb = new InlineKeyboard()
    .text('🔁 Scheduled Tasks', 'automation:scheduled').row()
    .text('🎯 Trigger Rules', 'automation:triggers').row()
    .text('🤖 Auto-Merge Rules', 'automation:automerge').row()
    .text('📤 Bulk Actions', 'automation:bulk').row()
    .text('⬅️ Back to Menu', 'menu:main');
  await ctx.editOrReply('⚡ Advanced Automation\n\nSet up rules that run without you tapping anything.', { reply_markup: kb });
}

function registerAutomationMenu(bot) {
  bot.callbackQuery('menu:automation', async (ctx) => { await renderAutomationMenu(ctx); await ctx.answerCallbackQuery(); });

  bot.callbackQuery('automation:scheduled', async (ctx) => {
    const result = await query('SELECT * FROM scheduled_tasks WHERE telegram_user_id = $1 AND enabled = true', [ctx.from.id]);
    let body = `🔁 Scheduled Tasks (${result.rows.length} active)\n\n`;
    result.rows.forEach((t) => (body += `⏰ ${t.cron_expression} — ${t.task_type}\n`));
    const kb = new InlineKeyboard().text('➕ New Scheduled Task', 'automation:scheduled:new').row().text('⬅️ Back to Automation', 'menu:automation');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('automation:scheduled:new', async (ctx) => {
    const kb = new InlineKeyboard()
      .text('📊 Repo Summary (daily 9am)', 'automation:scheduled:add:repo_summary:0 9 * * *').row()
      .text('🧹 Delete Merged Branches (weekly)', 'automation:scheduled:add:delete_merged_branches:0 8 * * 1').row()
      .text('⬅️ Cancel', 'automation:scheduled');
    await ctx.editOrReply('🔁 What should run on a schedule?', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^automation:scheduled:add:(.+):(.+)$/, async (ctx) => {
    await query('INSERT INTO scheduled_tasks (telegram_user_id, task_type, cron_expression) VALUES ($1, $2, $3)', [ctx.from.id, ctx.match[1], ctx.match[2]]);
    await ctx.answerCallbackQuery('Scheduled!');
    const result = await query('SELECT * FROM scheduled_tasks WHERE telegram_user_id = $1 AND enabled = true', [ctx.from.id]);
    let body = `🔁 Scheduled Tasks (${result.rows.length} active)\n\n`;
    result.rows.forEach((t) => (body += `⏰ ${t.cron_expression} — ${t.task_type}\n`));
    await ctx.editOrReply(body, { reply_markup: new InlineKeyboard().text('⬅️ Back to Automation', 'menu:automation') });
  });

  bot.callbackQuery('automation:triggers', async (ctx) => {
    const result = await query('SELECT * FROM trigger_rules WHERE telegram_user_id = $1 AND enabled = true', [ctx.from.id]);
    let body = `🎯 Trigger Rules (${result.rows.length} active)\n\n`;
    result.rows.forEach((r) => (body += `⚡ When: ${r.trigger_event}\n   Do: ${r.action_type}\n\n`));
    const kb = new InlineKeyboard().text('⬅️ Back to Automation', 'menu:automation');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('automation:automerge', async (ctx) => {
    const result = await query('SELECT * FROM automerge_rules WHERE telegram_user_id = $1 AND enabled = true', [ctx.from.id]);
    let body = `🤖 Auto-Merge Rules (${result.rows.length} active)\n\n`;
    result.rows.forEach((r) => (body += `${r.repo_full_name} (${r.target_branch}) — ${r.merge_method}\n`));
    await ctx.editOrReply(body || '🤖 No auto-merge rules configured yet. Set one up from a repo\'s detail screen.', { reply_markup: new InlineKeyboard().text('⬅️ Back to Automation', 'menu:automation') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('automation:bulk', async (ctx) => {
    const kb = new InlineKeyboard()
      .text('🧹 Close stale issues — all repos', 'automation:bulk:close_stale').row()
      .text('🏷️ Delete merged branches — all repos', 'automation:bulk:delete_merged').row()
      .text('⬅️ Back to Automation', 'menu:automation');
    await ctx.editOrReply('📤 Bulk Actions\n\nRun one action across multiple repos at once.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('automation:bulk:delete_merged', async (ctx) => {
    const reposApi = require('../../github/repos');
    const branchesApi = require('../../github/branches');
    const allRepos = await reposApi.listRepos(ctx.from.id, { perPage: 20, sort: 'updated' });
    await ctx.answerCallbackQuery('Running...');
    let totalDeleted = 0;
    for (const r of allRepos) {
      const [owner, name] = r.full_name.split('/');
      try {
        const deleted = await branchesApi.deleteMergedBranches(ctx.from.id, owner, name, r.default_branch);
        totalDeleted += deleted.length;
      } catch (_) { /* continue with next repo */ }
    }
    await ctx.reply(`✅ Bulk action complete\n\n${totalDeleted} merged branches deleted across ${allRepos.length} repos.`);
  });
}

module.exports = { registerAutomationMenu, renderAutomationMenu };
