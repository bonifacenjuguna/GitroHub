'use strict';

const { Bot } = require('grammy');
const env = require('../config/env');
const logger = require('../utils/logger');

const ownerGate = require('./middleware/ownerGate');
const { sessionMiddleware } = require('./middleware/session');
const { inFlightGuard, identitySync } = require('./middleware/guards');
const contextExtensions = require('./middleware/contextExtensions');

const { registerMainMenu } = require('./menus/mainMenu');
const { registerRepositoriesMenu } = require('./menus/repositories');
const { registerRepoDetail } = require('./menus/repoDetail');
const { registerRepoDelete } = require('./menus/repoDelete');
const { registerRepoEdit } = require('./menus/repoEdit');
const { registerBranches } = require('./menus/branches');
const { registerCommits } = require('./menus/commits');
const { registerFiles } = require('./menus/files');
const { registerPullRequests } = require('./menus/pullRequests');
const { registerIssues } = require('./menus/issues');
const { registerActions } = require('./menus/actionsMenu');
const { registerReleases } = require('./menus/releases');
const { registerUploadMenu } = require('./menus/upload');
const { registerSecurityMenu } = require('./menus/security');
const { registerSettingsMenu } = require('./menus/settings');
const { registerAutomationMenu } = require('./menus/automation');
const { registerSearchMenu } = require('./menus/search');
const { registerHelpMenu } = require('./menus/help');
const { registerRepoCreateImport } = require('./menus/repoCreateImport');
const { registerDevTools } = require('./menus/devTools');
const { registerAnalytics } = require('./menus/analytics');
const { registerGists } = require('./menus/gists');

const { registerUtilityCommands } = require('./commands/utilityCommands');
const { registerPendingActionHandler } = require('./handlers/pendingActionHandler');
const { registerUrlDetection } = require('./handlers/urlDetection');

function createBot() {
  const bot = new Bot(env.BOT_TOKEN);

  // --- Middleware order matters ---
  // 1. Owner gate FIRST — strangers are dropped before anything else runs.
  bot.use(ownerGate());
  // 2. Context helpers (ctx.editOrReply)
  bot.use(contextExtensions());
  // 3. Session (Redis-backed)
  bot.use(sessionMiddleware());
  // 4. Duplicate-tap guard
  bot.use(inFlightGuard());
  // 5. Keep Telegram identity fields fresh in Postgres
  bot.use(identitySync());

  // --- Commands ---
  registerMainMenu(bot);
  registerUtilityCommands(bot);

  // --- Menus (order doesn't matter much here, all are distinct callback patterns) ---
  registerRepositoriesMenu(bot);
  registerRepoDetail(bot);
  registerRepoDelete(bot);
  registerRepoEdit(bot);
  registerRepoCreateImport(bot);
  registerBranches(bot);
  registerCommits(bot);
  registerFiles(bot);
  registerPullRequests(bot);
  registerIssues(bot);
  registerActions(bot);
  registerReleases(bot);
  registerUploadMenu(bot);
  registerSecurityMenu(bot);
  registerSettingsMenu(bot);
  registerAutomationMenu(bot);
  registerSearchMenu(bot);
  registerHelpMenu(bot);
  registerDevTools(bot);
  registerAnalytics(bot);
  registerGists(bot);

  // --- Text/document handlers (order matters: pendingAction consumes first, URL detection is fallback) ---
  registerPendingActionHandler(bot);
  registerUrlDetection(bot);

  bot.catch((err) => {
    logger.error({ err: err.error, updateId: err.ctx?.update?.update_id }, 'Unhandled bot error');
  });

  return bot;
}

module.exports = { createBot };
