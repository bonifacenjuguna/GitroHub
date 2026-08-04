const { Telegraf, Scenes, session } = require('telegraf');
const config = require('./config');
const ownerGate = require('./middleware/ownerGate');
const redisStore = require('./middleware/redisSessionStore');

const startHandler = require('./handlers/start');
const myRepos = require('./handlers/myRepos');
const repoView = require('./handlers/repoView');
const browseFiles = require('./handlers/browseFiles');
const settings = require('./handlers/settings');
const activityLog = require('./handlers/activityLog');
const search = require('./handlers/search');
const format = require('./lib/format');

const createRepoScene = require('./scenes/createRepo');
const renameRepoScene = require('./scenes/renameRepo');
const uploadFileScene = require('./scenes/uploadFile');
const editFileScene = require('./scenes/editFile');

function createBot() {
  const bot = new Telegraf(config.BOT_TOKEN);

  // 1) Owner-only gate — MUST be first
  bot.use(ownerGate());

  // 2) Redis-backed session (required by Scenes for wizard state)
  bot.use(session({ store: redisStore }));

  // 3) Scenes stage
  const stage = new Scenes.Stage([createRepoScene, renameRepoScene, uploadFileScene, editFileScene]);
  bot.use(stage.middleware());

  // ─── Commands ─────────────────────────────────────────────
  bot.start(startHandler.handleStart);

  // ─── BBTB (Reply Keyboard) text handlers ───────────────────
  bot.hears('📁 My Repos', (ctx) => myRepos.showMyRepos(ctx));
  bot.hears('➕ New Repo', (ctx) => ctx.scene.enter('createRepo'));
  bot.hears('🔍 Search Repo', async (ctx) => {
    ctx.session.awaitingSearch = true;
    await ctx.reply('🔍 Type a repo name/keyword, or paste a GitHub repo link.', require('./keyboards/bbtb').cancelOnly);
  });
  bot.hears('⚙️ Settings', (ctx) => settings.showSettings(ctx));

  bot.hears('⬆️ Back to Menu', async (ctx) => {
    ctx.session.awaitingSearch = false;
    await ctx.reply('📍 Main Menu', require('./keyboards/bbtb').mainMenu);
  });

  bot.hears('🔎 Filter', (ctx) => myRepos.showFilterMenu(ctx));
  bot.hears('↕️ Sort', (ctx) => myRepos.showSortMenu(ctx));
  bot.hears('🔄 Refresh', (ctx) => myRepos.showMyRepos(ctx));

  bot.hears('⬅️ Back to Repos', async (ctx) => {
    await myRepos.showMyRepos(ctx);
  });

  bot.hears('⬆️ Upload', async (ctx) => {
    const repoName = ctx.session.currentRepo;
    if (!repoName) return ctx.reply('Open a repo first from 📁 My Repos.');
    await ctx.scene.enter('uploadFile', { repoName });
  });
  bot.hears('📁 Browse Files', async (ctx) => {
    const repoName = ctx.session.currentRepo;
    if (!repoName) return ctx.reply('Open a repo first from 📁 My Repos.');
    await browseFiles.showDirectory(ctx, repoName, '');
  });
  bot.hears('⬇️ Download Repo', async (ctx) => {
    const repoName = ctx.session.currentRepo;
    if (!repoName) return ctx.reply('Open a repo first from 📁 My Repos.');
    await repoView.downloadRepo(ctx, repoName);
  });
  bot.hears('🔒 Visibility', async (ctx) => {
    const repoName = ctx.session.currentRepo;
    if (!repoName) return ctx.reply('Open a repo first from 📁 My Repos.');
    await repoView.askToggleVisibility(ctx, repoName);
  });

  bot.hears('🔍 Search Files', async (ctx) => {
    ctx.session.awaitingFileSearch = true;
    await ctx.reply('🔍 Type a filename or keyword to search across all files.', require('./keyboards/bbtb').cancelOnly);
  });
  bot.hears('⬆️ Back to Repo', async (ctx) => {
    const repoName = ctx.session.currentRepo;
    if (repoName) await repoView.showRepoView(ctx, repoName);
  });

  bot.hears('🔔 Notifications', (ctx) => settings.showNotifications(ctx));
  bot.hears('📜 Activity', (ctx) => activityLog.showActivity(ctx));
  bot.hears('🚪 Disconnect', (ctx) => settings.askDisconnect(ctx));
  bot.hears('🔄 Refresh Status', (ctx) => settings.showSettings(ctx));
  bot.hears('⬆️ Back to Settings', (ctx) => settings.showSettings(ctx));

  bot.hears('🔁 Search Again', async (ctx) => {
    ctx.session.awaitingSearch = true;
    await ctx.reply('🔍 Type a repo name/keyword, or paste a GitHub repo link.');
  });

  bot.hears('📤 Upload Another', async (ctx) => {
    const repoName = ctx.session.currentRepo;
    if (repoName) await ctx.scene.enter('uploadFile', { repoName });
  });

  bot.hears('❌ Cancel', async (ctx) => {
    ctx.session.awaitingSearch = false;
    ctx.session.awaitingFileSearch = false;
    await ctx.reply('Cancelled.', require('./keyboards/bbtb').mainMenu);
  });

  // ─── Free-text input router (search / file-search) ─────────
  bot.on('text', async (ctx, next) => {
    if (ctx.scene && ctx.scene.current) return next(); // scene handles its own text

    if (ctx.session.awaitingSearch) {
      ctx.session.awaitingSearch = false;
      return search.handleSearchInput(ctx, ctx.message.text);
    }
    if (ctx.session.awaitingFileSearch) {
      ctx.session.awaitingFileSearch = false;
      return browseFiles.searchFiles(ctx, ctx.session.currentRepo, ctx.message.text);
    }
    return next();
  });

  // ─── Inline callback_query router ───────────────────────────
  bot.on('callback_query', async (ctx, next) => {
    const data = ctx.callbackQuery.data || '';

    // Repo list / filter / sort / pagination
    if (data.startsWith('repo:') && !data.includes(':rename:') && !data.includes(':delete:') && !data.includes(':visibility:')) {
      await ctx.answerCbQuery();
      const repoName = data.split('repo:')[1];
      return repoView.showRepoView(ctx, repoName);
    }
    if (data.startsWith('repos:page:')) {
      await ctx.answerCbQuery();
      myRepos.setPage(ctx.from.id, Number(data.split(':')[2]));
      return myRepos.showMyRepos(ctx, { edit: true });
    }
    if (data === 'repos:back') {
      await ctx.answerCbQuery();
      return myRepos.showMyRepos(ctx, { edit: true });
    }
    if (data.startsWith('filter:')) {
      await ctx.answerCbQuery();
      myRepos.setFilter(ctx.from.id, data.split(':')[1]);
      return myRepos.showMyRepos(ctx, { edit: true });
    }
    if (data.startsWith('sort:')) {
      await ctx.answerCbQuery();
      myRepos.setSort(ctx.from.id, data.split(':')[1]);
      return myRepos.showMyRepos(ctx, { edit: true });
    }

    // Repo actions
    if (data.startsWith('repo:rename:')) {
      await ctx.answerCbQuery();
      const repoName = data.split('repo:rename:')[1];
      return ctx.scene.enter('renameRepo', { repoName });
    }
    if (data.startsWith('repo:delete:confirm:')) {
      await ctx.answerCbQuery();
      return repoView.executeDeleteRepo(ctx, data.split('repo:delete:confirm:')[1]);
    }
    if (data.startsWith('repo:delete:cancel:')) {
      await ctx.answerCbQuery();
      return ctx.reply('Cancelled.');
    }
    if (data.startsWith('repo:delete:')) {
      await ctx.answerCbQuery();
      return repoView.askDeleteRepo(ctx, data.split('repo:delete:')[1]);
    }
    if (data.startsWith('repo:visibility:confirm:')) {
      await ctx.answerCbQuery();
      return repoView.executeToggleVisibility(ctx, data.split('repo:visibility:confirm:')[1]);
    }
    if (data.startsWith('repo:visibility:cancel:')) {
      await ctx.answerCbQuery();
      return ctx.reply('Cancelled.');
    }

    // File browsing
    if (data.startsWith('browse:dir:')) {
      await ctx.answerCbQuery();
      return browseFiles.showDirectory(ctx, ctx.session.currentRepo, data.split('browse:dir:')[1]);
    }
    if (data.startsWith('browse:file:')) {
      await ctx.answerCbQuery();
      return browseFiles.showFileActions(ctx, ctx.session.currentRepo, data.split('browse:file:')[1]);
    }
    if (data.startsWith('browse:parent:')) {
      await ctx.answerCbQuery();
      const filePath = data.split('browse:parent:')[1];
      const parent = filePath.split('/').slice(0, -1).join('/');
      return browseFiles.showDirectory(ctx, ctx.session.currentRepo, parent);
    }
    if (data.startsWith('file:view:')) {
      await ctx.answerCbQuery();
      return browseFiles.viewFileContent(ctx, ctx.session.currentRepo, data.split('file:view:')[1]);
    }
    if (data.startsWith('file:raw:')) {
      await ctx.answerCbQuery();
      return browseFiles.sendFileAsDocument(ctx, ctx.session.currentRepo, data.split('file:raw:')[1]);
    }
    if (data.startsWith('file:edit:')) {
      await ctx.answerCbQuery();
      const filePath = data.split('file:edit:')[1];
      return ctx.scene.enter('editFile', { repoName: ctx.session.currentRepo, filePath });
    }
    if (data.startsWith('file:delete:confirm:')) {
      await ctx.answerCbQuery();
      return browseFiles.executeDeleteFile(ctx, ctx.session.currentRepo, data.split('file:delete:confirm:')[1]);
    }
    if (data.startsWith('file:delete:cancel:')) {
      await ctx.answerCbQuery();
      return ctx.reply('Cancelled.');
    }
    if (data.startsWith('file:delete:')) {
      await ctx.answerCbQuery();
      return browseFiles.askDeleteFile(ctx, ctx.session.currentRepo, data.split('file:delete:')[1]);
    }

    // External repo (search-detected link)
    if (data === 'external:download') {
      await ctx.answerCbQuery();
      return search.downloadExternalZip(ctx);
    }
    if (data === 'external:fork') {
      await ctx.answerCbQuery();
      return search.forkExternal(ctx);
    }
    if (data === 'external:fork:confirm') {
      await ctx.answerCbQuery();
      return search.executeForkExternal(ctx);
    }
    if (data === 'external:fork:cancel' || data === 'external:cancel') {
      await ctx.answerCbQuery();
      return ctx.reply('Cancelled.');
    }

    // Settings / notifications / activity
    if (data.startsWith('notif:toggle:')) {
      await ctx.answerCbQuery();
      return settings.toggleNotification(ctx, data.split('notif:toggle:')[1]);
    }
    if (data === 'settings:disconnect:confirm') {
      await ctx.answerCbQuery();
      return settings.executeDisconnect(ctx);
    }
    if (data === 'settings:disconnect:cancel') {
      await ctx.answerCbQuery();
      return ctx.reply('Cancelled.');
    }
    if (data === 'settings:back') {
      await ctx.answerCbQuery();
      return settings.showSettings(ctx);
    }
    if (data.startsWith('activity:page:')) {
      await ctx.answerCbQuery();
      const [, , page, errorsOnly] = data.split(':');
      return activityLog.showActivity(ctx, { page: Number(page), errorsOnly: errorsOnly === 'true', edit: true });
    }
    if (data.startsWith('activity:filter:')) {
      await ctx.answerCbQuery();
      const errorsOnly = data.split('activity:filter:')[1] === 'true';
      return activityLog.showActivity(ctx, { page: 1, errorsOnly, edit: true });
    }

    return next();
  });

  // ─── Global error handler ────────────────────────────────────
  bot.catch(async (err, ctx) => {
    console.error('Bot error:', err);
    try {
      await ctx.reply(format.errorMessage('Something went wrong', err.message || 'unexpected error', 'Try again, or go back to the main menu.'));
    } catch (_) { /* swallow */ }
  });

  return bot;
}

module.exports = createBot;
