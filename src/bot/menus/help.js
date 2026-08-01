'use strict';

const { InlineKeyboard } = require('grammy');
const pkg = require('../../../package.json');
const env = require('../../config/env');

async function renderHelpMenu(ctx) {
  const kb = new InlineKeyboard()
    .text('🚀 Getting Started', 'help:start').row()
    .text('❓ FAQ', 'help:faq').row()
    .text('📜 Terms & Policies', 'help:terms').row()
    .text('ℹ️ About GitroHub', 'help:about').row()
    .text('⬅️ Back to Menu', 'menu:main');
  await ctx.editOrReply('❓ Help & Support\n\nWhat do you need help with?', { reply_markup: kb });
}

function registerHelpMenu(bot) {
  bot.callbackQuery('menu:help', async (ctx) => { await renderHelpMenu(ctx); await ctx.answerCallbackQuery(); });

  bot.callbackQuery('help:start', async (ctx) => {
    const kb = new InlineKeyboard().text('🔐 Connect GitHub Now', 'menu:security').row().text('⬅️ Back to Help', 'menu:help');
    await ctx.editOrReply(
      `🚀 Getting Started with GitroHub\n\n1️⃣ Connect your GitHub account\n2️⃣ Browse or create a repository\n3️⃣ Upload files or make changes directly in chat\n4️⃣ Manage PRs, issues, and releases — all here\n\nTip: paste any GitHub URL directly into this chat to instantly preview or download it.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('help:faq', async (ctx) => {
    const kb = new InlineKeyboard().text('⬅️ Back to Help', 'menu:help');
    await ctx.editOrReply(
      `❓ FAQ\n\n` +
      `Is my GitHub token safe?\nYes — encrypted with AES-256-GCM, unique key per account.\n\n` +
      `What happens if I disconnect?\nYour token is deleted and revoked on GitHub's side immediately.\n\n` +
      `Why was my upload rejected?\nCheck the specific error message — it always states exactly what failed.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('help:about', async (ctx) => {
    const kb = new InlineKeyboard().text('⬅️ Back to Help', 'menu:help');
    await ctx.editOrReply(
      `ℹ️ About GitroHub\n\nVersion ${pkg.version}\n\nYour complete GitHub workspace in Telegram.\nManage, automate, and enhance your GitHub workflow without leaving Telegram.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('help:terms', async (ctx) => {
    const kb = new InlineKeyboard()
      .url('📄 Terms of Service', `${env.DOMAIN}/legal/terms`).row()
      .url('🔒 Privacy Policy', `${env.DOMAIN}/legal/privacy`).row()
      .url('⚖️ Acceptable Use Policy', `${env.DOMAIN}/legal/acceptable-use`).row()
      .text('⬅️ Back to Help', 'menu:help');
    await ctx.editOrReply('📜 Terms & Policies\n\nFull legal documents are hosted at gitrohub.vercel.app/legal — also included in this project\'s /docs folder.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerHelpMenu, renderHelpMenu };
