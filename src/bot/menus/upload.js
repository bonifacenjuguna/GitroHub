'use strict';

const { InlineKeyboard } = require('grammy');
const filesApi = require('../../github/files');
const { extractZip, computeZipDiff, commitZipBatch } = require('../../github/zipPipeline');
const { formatBytes } = require('../../utils/format');
const { formatError } = require('../../utils/errors');
const { logAction } = require('../../db/postgres/activityLog');

function enc(s) { return encodeURIComponent(s); }

async function renderUploadEntry(ctx) {
  const kb = new InlineKeyboard()
    .text('📄 Single File', 'upload:target:file').text('📦 ZIP Project', 'upload:target:zip').row()
    .text('⬅️ Back to Menu', 'menu:main');
  await ctx.editOrReply('📁 Upload / Deploy\n\nWhat do you want to upload?', { reply_markup: kb });
}

/** "Upload Here" shortcut from Browse Files — target already known, skip straight to receiving the file. */
async function startUploadHere(ctx, fullName, branch, folderPath) {
  ctx.session.uploadState = { targetRepo: fullName, targetBranch: branch, targetPath: folderPath, mode: 'here' };
  const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
  await ctx.editOrReply(
    `📤 Upload to: ${folderPath || '(root)'}/\nBranch: ${branch}\n\nSend a file, or a .zip to upload multiple files into this folder.`,
    { reply_markup: kb }
  );
}

async function handleIncomingDocument(ctx) {
  const state = ctx.session.uploadState;
  if (!state) return; // no upload in progress — ignore silently, other handlers may care

  const doc = ctx.message.document;
  const isZip = doc.mime_type === 'application/zip' || doc.file_name.toLowerCase().endsWith('.zip');

  const file = await ctx.api.getFile(doc.file_id);
  const buffer = await downloadTelegramFile(ctx, file.file_path);

  if (isZip) {
    return handleZipUpload(ctx, state, buffer);
  }
  return handleSingleFileUpload(ctx, state, buffer, doc.file_name);
}

async function downloadTelegramFile(ctx, filePath) {
  const env = require('../../config/env');
  const url = `https://api.telegram.org/file/bot${env.BOT_TOKEN}/${filePath}`;
  const res = await fetch(url);
  return Buffer.from(await res.arrayBuffer());
}

async function handleSingleFileUpload(ctx, state, buffer, fileName) {
  const [owner, repoName] = state.targetRepo.split('/');
  const targetPath = state.targetPath ? `${state.targetPath.replace(/\/$/, '')}/${fileName}` : fileName;

  await ctx.reply(`📄 Received: ${fileName} (${formatBytes(buffer.length)})\n\nChecking ${targetPath}...`);

  const diff = await filesApi.diffAgainstRepo(ctx.from.id, owner, repoName, targetPath, state.targetBranch, buffer);

  if (diff.status === 'unchanged') {
    ctx.session.uploadState = null;
    const kb = new InlineKeyboard().text('⬅️ Back to Repo', `repo:open:${enc(state.targetRepo)}`);
    return ctx.reply(`ℹ️ No changes detected.\n\n${targetPath} is identical to what's already there.`, { reply_markup: kb });
  }

  ctx.session.pendingAction = {
    type: 'commit_message',
    payload: {
      kind: 'single',
      fullName: state.targetRepo, branch: state.targetBranch,
      path: targetPath, buffer: buffer.toString('base64'),
      existingSha: diff.existing?.sha || null, status: diff.status,
    },
  };

  const label = diff.status === 'new' ? `🆕 New file: ${targetPath} (${formatBytes(buffer.length)})` : `📝 Changes detected in ${targetPath}`;
  const kb = new InlineKeyboard().text('✅ Use Default Message', 'upload:commit:default').row().text('❌ Cancel', 'flow:cancel');
  await ctx.reply(`${label}\n\nSend a commit message, or use the default.`, { reply_markup: kb });
}

async function handleCommitMessage(ctx, payload, text) {
  const message = text || `Update ${payload.path} via GitroHub`;
  await commitPendingPayload(ctx, payload, message);
}

async function commitPendingPayload(ctx, payload, message) {
  const [owner, repoName] = payload.fullName.split('/');

  if (payload.kind === 'single') {
    const buffer = Buffer.from(payload.buffer, 'base64');
    const result = await filesApi.commitFile(ctx.from.id, owner, repoName, {
      path: payload.path, branch: payload.branch, content: buffer, message, existingSha: payload.existingSha,
    });
    await logAction(ctx.from.id, 'push', payload.fullName, { path: payload.path });
    ctx.session.uploadState = null;
    const kb = new InlineKeyboard()
      .text('📄 View Commit', `commit:${enc(payload.fullName)}:${result.commit.sha}`)
      .text('⬅️ Back to Repo', `repo:open:${enc(payload.fullName)}`);
    return ctx.reply(`✅ Committed to ${payload.branch}\n${result.commit.sha.slice(0, 7)} — "${message}"`, { reply_markup: kb });
  }

  if (payload.kind === 'zip') {
    // A multi-file commit can genuinely take longer than a few seconds
    // (building blobs for every file, then one tree + commit + ref
    // update). Acknowledge immediately so the user isn't staring at
    // silence wondering whether the tap registered — the actual commit
    // continues in the background regardless of this message.
    await ctx.reply('⏳');

    try {
      const result = await commitZipBatch(ctx.from.id, owner, repoName, payload.branch, payload.filesToCommit, message);
      await logAction(ctx.from.id, 'push', payload.fullName, { fileCount: result.committedPaths.length });
      ctx.session.uploadState = null;
      const kb = new InlineKeyboard()
        .text('📄 View Commit', `commit:${enc(payload.fullName)}:${result.commitSha}`).row()
        .text('🔀 Create Pull Request', `pr:${enc(payload.fullName)}:create:${enc(payload.branch)}`)
        .row().text('⬅️ Back to Repo', `repo:open:${enc(payload.fullName)}`).text('🏠 Main Menu', 'menu:main');
      return ctx.reply(`✅ Committed to ${payload.branch}\n${result.commitSha.slice(0, 7)} — ${result.committedPaths.length} files changed — "${message}"`, { reply_markup: kb });
    } finally {
      // Always clear the busy flag, success or failure, so a genuine
      // error never leaves the upload flow permanently stuck for this
      // session — the top-level try/catch in the callback handler below
      // still reports the actual error to the user.
      if (ctx.session.uploadState) ctx.session.uploadState.committing = false;
    }
  }
}

async function handleZipUpload(ctx, state, buffer) {
  await ctx.reply('📦 Extracting...');
  const { wrapperDetected, files } = extractZip(buffer);

  ctx.session.uploadState = { ...state, zipBuffer: buffer.toString('base64'), files: null }; // buffer stored short-term only

  if (wrapperDetected) {
    const kb = new InlineKeyboard()
      .text('✅ Strip wrapper', `upload:zip:strip:true`)
      .text('📁 Keep as folder', `upload:zip:strip:false`);
    ctx.session.uploadState.pendingWrapper = wrapperDetected;
    return ctx.reply(`Detected a wrapper folder: ${wrapperDetected}/\nIts contents will be treated as the project root.`, { reply_markup: kb });
  }

  return proceedWithZipDiff(ctx, files);
}

async function proceedWithZipDiff(ctx, files) {
  const state = ctx.session.uploadState;
  const [owner, repoName] = state.targetRepo.split('/');

  const results = await computeZipDiff(ctx.from.id, owner, repoName, state.targetBranch, state.targetPath, files, { applyGitignore: true });

  if (results.excludedCount > 0) {
    await ctx.reply(`Applying .gitignore rules...\nExcluded ${results.excludedCount} files.`);
  }

  const totalChanges = results.new.length + results.modified.length;
  if (totalChanges === 0) {
    ctx.session.uploadState = null;
    const kb = new InlineKeyboard().text('⬅️ Back to Repo', `repo:open:${enc(state.targetRepo)}`);
    return ctx.reply('ℹ️ No changes detected. Nothing to commit.', { reply_markup: kb });
  }

  ctx.session.uploadState.diffResults = {
    new: results.new.map((f) => f.fullPath),
    modified: results.modified.map((f) => f.fullPath),
  };
  ctx.session.uploadState.filesToCommit = [...results.new, ...results.modified];

  let body = `📊 Comparison vs ${state.targetBranch}\n\n`;
  body += `🆕 New files (${results.new.length})\n`;
  body += `📝 Modified files (${results.modified.length})\n`;
  body += `✅ Unchanged (${results.unchanged.length})`;

  const kb = new InlineKeyboard()
    .text('✅ Commit All', 'upload:zip:commit_all').text('❌ Cancel', 'flow:cancel');
  await ctx.reply(body, { reply_markup: kb });
}

function registerUploadMenu(bot) {
  bot.callbackQuery('menu:upload', async (ctx) => {
    await renderUploadEntry(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('upload:target:file', async (ctx) => {
    ctx.session.uploadState = { mode: 'file', awaitingTargetSelection: true };
    await ctx.editOrReply('📤 Where should this be uploaded?', {
      reply_markup: new InlineKeyboard().text('📦 Existing Repo', 'upload:pick_repo').row().text('⬅️ Cancel', 'flow:cancel'),
    });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('upload:target:zip', async (ctx) => {
    ctx.session.uploadState = { mode: 'zip', awaitingTargetSelection: true };
    await ctx.editOrReply('📤 Where should this be uploaded?', {
      reply_markup: new InlineKeyboard().text('📦 Existing Repo', 'upload:pick_repo').row().text('⬅️ Cancel', 'flow:cancel'),
    });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('upload:pick_repo', async (ctx) => {
    const reposApi = require('../../github/repos');
    const list = await reposApi.listRepos(ctx.from.id, { perPage: 8, sort: 'updated' });
    const kb = new InlineKeyboard();
    list.forEach((r) => kb.text(r.full_name, `upload:set_repo:${enc(r.full_name)}:${enc(r.default_branch)}`).row());
    kb.text('⬅️ Cancel', 'flow:cancel');
    await ctx.editOrReply('📦 Select a repository', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^upload:set_repo:(.+):(.+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const branch = decodeURIComponent(ctx.match[2]);
    ctx.session.uploadState = { ...ctx.session.uploadState, targetRepo: fullName, targetBranch: branch, targetPath: '' };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply(`Send the file to upload (or a .zip for a full project).`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^upload:zip:strip:(true|false)$/, async (ctx) => {
    const strip = ctx.match[1] === 'true';
    const state = ctx.session.uploadState;
    const buffer = Buffer.from(state.zipBuffer, 'base64');
    const { files } = extractZip(buffer); // re-extract; wrapper stripping is already the default behavior of extractZip
    const finalFiles = strip ? files : files.map((f) => ({ ...f, path: `${state.pendingWrapper}/${f.path}` }));
    await ctx.answerCallbackQuery();
    await proceedWithZipDiff(ctx, finalFiles);
  });

  bot.callbackQuery('upload:zip:commit_all', async (ctx) => {
    ctx.session.pendingAction = {
      type: 'commit_message',
      payload: {
        kind: 'zip',
        fullName: ctx.session.uploadState.targetRepo,
        branch: ctx.session.uploadState.targetBranch,
        filesToCommit: ctx.session.uploadState.filesToCommit,
      },
    };
    const { diffResults } = ctx.session.uploadState;
    const defaultMsg = `Update project via GitroHub ZIP upload (${diffResults.modified.length} modified, ${diffResults.new.length} new)`;
    ctx.session.pendingAction.payload.defaultMessage = defaultMsg;
    const kb = new InlineKeyboard().text('✅ Use Default', 'upload:commit:default').row().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply(`💬 Commit Message\n\nDefault: "${defaultMsg}"\n\nSend a custom message, or use the default.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('upload:commit:default', async (ctx) => {
    const pending = ctx.session.pendingAction;
    if (!pending) return ctx.answerCallbackQuery();

    if (ctx.session.uploadState?.committing) {
      // A commit for this exact upload is already running (e.g. Telegram
      // redelivered this same tap while the first run was still in
      // progress). Acknowledge without starting a second, competing
      // commit — this is the actual fix for "many messages sent" /
      // "next tap does nothing", not just a longer timer.
      return ctx.answerCallbackQuery('Already committing — please wait for it to finish.');
    }
    if (ctx.session.uploadState) ctx.session.uploadState.committing = true;

    ctx.session.pendingAction = null;
    const message = pending.payload.defaultMessage || `Update ${pending.payload.path} via GitroHub`;
    await ctx.answerCallbackQuery();
    try {
      await commitPendingPayload(ctx, pending.payload, message);
    } catch (err) {
      if (ctx.session.uploadState) ctx.session.uploadState.committing = false;
      const formatted = formatError(err, { backCallback: 'menu:upload' });
      const kb = new InlineKeyboard();
      formatted.buttons.forEach((row) => { kb.row(); row.forEach((b) => kb.text(b.text, b.data)); });
      await ctx.reply(formatted.text, { reply_markup: kb });
    }
  });

  bot.callbackQuery('flow:cancel', async (ctx) => {
    ctx.session.uploadState = null;
    ctx.session.pendingAction = null;
    await ctx.answerCallbackQuery('Cancelled');
    const { renderMainMenu } = require('./mainMenu');
    await renderMainMenu(ctx);
  });

  bot.on('message:document', async (ctx, next) => {
    if (!ctx.session.uploadState) return next();
    try {
      await handleIncomingDocument(ctx);
    } catch (err) {
      const formatted = formatError(err, { backCallback: 'menu:upload' });
      const kb = new InlineKeyboard();
      formatted.buttons.forEach((row) => { kb.row(); row.forEach((b) => kb.text(b.text, b.data)); });
      await ctx.reply(formatted.text, { reply_markup: kb });
    }
  });
}

module.exports = { registerUploadMenu, startUploadHere, handleCommitMessage };
