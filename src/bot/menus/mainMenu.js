'use strict';

const { InlineKeyboard } = require('grammy');
const { isConnected, getUser } = require('../../db/postgres/users');
const { listPulls } = require('../../github/pullRequests');
const { getRateLimitSnapshot } = require('../../db/redis/cache');
const logger = require('../../utils/logger');

function mainMenuKeyboard() {
  return new InlineKeyboard()
    .text('📦 Repositories', 'menu:repos').text('📁 Upload/Deploy', 'menu:upload').row()
    .text('🚀 Smart Deploy', 'flow:smart_deploy').text('🔍 Search Code', 'menu:search').row()
    .text('⚡ Automation', 'menu:automation').text('📊 Analytics', 'menu:analytics_hub').row()
    .text('🔐 Account & Security', 'menu:security').text('⚙️ Settings', 'menu:settings').row()
    .text('📋 Gists', 'menu:gists').text('🛠️ Developer Tools', 'menu:devtools').row()
    .text('❓ Help', 'menu:help');
}

async function renderMainMenu(ctx) {
  const user = await getUser(ctx.from.id);
  const connected = Boolean(user?.encrypted_token);
  const firstName = ctx.from.first_name || 'there';

  let body;
  if (!connected) {
    body =
      `👋 Welcome to GitroHub\n\n` +
      `Your complete GitHub workspace, right here in Telegram.\n\n` +
      `You're not connected to GitHub yet. Connect your account to get started — it takes 10 seconds.`;
    const kb = new InlineKeyboard().text('🔗 Connect GitHub', 'auth:connect').row().text('❓ What is GitroHub?', 'help:about');
    return ctx.editOrReply(body, { reply_markup: kb });
  }

  let prCount = 0;
  try {
    // Lightweight best-effort stat, never blocks the menu if it fails
    const prs = await listPulls(ctx.from.id, user.github_username, 'gitrohub-bot').catch(() => []);
    prCount = prs.length;
  } catch (err) {
    logger.debug({ err }, 'Could not compute quick stats for main menu');
  }

  body =
    `👋 Welcome back, ${firstName}!\n\n` +
    `🔗 Connected as @${user.github_username}\n\n` +
    `What would you like to do?`;

  return ctx.editOrReply(body, { reply_markup: mainMenuKeyboard() });
}

function registerMainMenu(bot) {
  bot.command('start', async (ctx) => {
    await renderMainMenu(ctx);
  });

  bot.command('menu', async (ctx) => {
    await renderMainMenu(ctx);
  });

  bot.callbackQuery('menu:main', async (ctx) => {
    await renderMainMenu(ctx);
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerMainMenu, renderMainMenu, mainMenuKeyboard };
