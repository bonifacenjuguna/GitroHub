const { Scenes, Markup } = require('telegraf');
const AdmZip = require('adm-zip');
const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const { gitBlobSha } = require('../lib/gitHash');
const config = require('../config');

const PATH_EXAMPLES =
  'Examples:\n' +
  '• src/index.js\n' +
  '• assets/images/logo.png\n' +
  '• config/settings.json\n' +
  '• (leave blank for root)';

const scene = new Scenes.WizardScene(
  'uploadFile',

  // Step 0 — entry
  async (ctx) => {
    ctx.wizard.state.repoName = ctx.wizard.state.repoName || ctx.scene.state.repoName;
    await ctx.reply(
      `📤 Send a file or a .zip (max ${format.formatBytes(config.MAX_ZIP_SIZE_BYTES)}) to upload to ${ctx.wizard.state.repoName}`,
      bbtb.cancelOnly
    );
    return ctx.wizard.next();
  },

  // Step 1 — receive document
  async (ctx) => {
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      await ctx.reply('Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (!ctx.message || !ctx.message.document) {
      await ctx.reply('Send a file as a document attachment, or ❌ Cancel.');
      return;
    }

    const doc = ctx.message.document;
    const isZip = doc.file_name.toLowerCase().endsWith('.zip');

    if (isZip && doc.file_size > config.MAX_ZIP_SIZE_BYTES) {
      await ctx.reply(format.errorMessage(
        'Zip exceeds size limit',
        `${doc.file_name} is ${format.formatBytes(doc.file_size)}, limit is ${format.formatBytes(config.MAX_ZIP_SIZE_BYTES)}`,
        'Please split or compress further, then resend.'
      ));
      return;
    }

    const fileLink = await ctx.telegram.getFileLink(doc.file_id);
    const res = await fetch(fileLink.href);
    const buffer = Buffer.from(await res.arrayBuffer());

    if (isZip) {
      return processZip(ctx, buffer);
    }
    return processSingleFile(ctx, buffer, doc.file_name);
  },

  // Step 2 — path choice for single file (skipped for zip, handled inline)
  async (ctx) => {
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:choose:root') {
      await ctx.answerCbQuery();
      ctx.wizard.state.pendingFiles[0].path = ctx.wizard.state.pendingFiles[0].filename;
      return showSummary(ctx);
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:choose:browse') {
      await ctx.answerCbQuery();
      await ctx.reply('Browsing isn\u2019t available in this simplified flow — please type the path instead.');
      return;
    }
    if (ctx.message && ctx.message.text === '⌨️ Type Path Instead') {
      await ctx.reply(`⌨️ Type the destination path.\n\n${PATH_EXAMPLES}`, bbtb.cancelWithBack);
      return;
    }
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      await ctx.reply('Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (ctx.message && ctx.message.text) {
      const path = ctx.message.text.trim();
      if (/\/\/|^\/|\s\/|\/\s/.test(path)) {
        await ctx.reply(format.errorMessage(
          'Invalid path',
          `"${path}" contains a double slash, leading slash, or space around a slash`,
          `${PATH_EXAMPLES}\n\nTry again.`
        ));
        return;
      }
      ctx.wizard.state.pendingFiles[0].path = path || ctx.wizard.state.pendingFiles[0].filename;
      return showSummary(ctx);
    }
  },

  // Step 3 — summary shown, wait for commit/cancel/list
  async (ctx) => {
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:summary:list') {
      await ctx.answerCbQuery();
      const list = ctx.wizard.state.pendingFiles
        .map((f) => `${statusIcon(f.status)} ${f.path}`)
        .join('\n');
      await ctx.reply(`📋 Files:\n${list}`);
      return;
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:cancel') {
      await ctx.answerCbQuery();
      await ctx.reply('Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:commit') {
      await ctx.answerCbQuery();
      const changed = ctx.wizard.state.pendingFiles.filter((f) => f.status !== 'unchanged');
      if (changed.length === 0) {
        await ctx.reply('⚠️ Nothing to commit — all files matched what\u2019s already in the repo.', bbtb.mainMenu);
        return ctx.scene.leave();
      }
      await ctx.reply('Write a commit message, or use default.', bbtb.cancelWithSkip);
      return ctx.wizard.next();
    }
    await ctx.reply('Tap 📋 View File List, ✅ Commit Changes, or ❌ Cancel above.');
  },

  // Step 4 — commit message, then commit
  async (ctx) => {
    let message = 'Update via GitroHub';
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      await ctx.reply('Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (ctx.message && ctx.message.text && ctx.message.text !== '⏭️ Skip') {
      message = ctx.message.text.trim();
    } else if (!(ctx.message && ctx.message.text === '⏭️ Skip')) {
      await ctx.reply('Send a commit message, tap ⏭️ Skip for default, or ❌ Cancel.');
      return;
    }

    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const changed = ctx.wizard.state.pendingFiles.filter((f) => f.status !== 'unchanged');
    try {
      const user = await github.getAuthenticatedUser(token);
      await github.commitMultipleFiles(
        token,
        user.login,
        ctx.wizard.state.repoName,
        changed.map((f) => ({ path: f.path, content: f.content })),
        message
      );
      await activity.log(ctx.from.id, '⬆️', `Uploaded ${changed.length} file(s) → ${ctx.wizard.state.repoName}`);
      await ctx.reply(
        `✅ Pushed ${changed.length} changes to ${ctx.wizard.state.repoName}\nCommit: "${message}"`,
        bbtb.mainMenu
      );
    } catch (err) {
      await activity.log(ctx.from.id, '⚠️', `Upload commit failed → ${ctx.wizard.state.repoName}`, { detail: err.message, isError: true });
      await ctx.reply(format.errorMessage('Upload failed', err.message, 'Try again.'), bbtb.mainMenu);
    }
    return ctx.scene.leave();
  }
);

function statusIcon(status) {
  return { new: '🆕', modified: '✏️', unchanged: '➖' }[status] || '•';
}

async function classifyFiles(ctx, files) {
  const token = await requireConnected(ctx);
  if (!token) return null;
  const user = await github.getAuthenticatedUser(token);

  let existingTree = [];
  try {
    existingTree = await github.getTree(token, user.login, ctx.wizard.state.repoName);
  } catch (_) {
    // empty/new repo — everything is new
  }
  const existingByPath = new Map(existingTree.map((e) => [e.path, e.sha]));

  return files.map((f) => {
    const existingSha = existingByPath.get(f.path);
    const localSha = gitBlobSha(f.content);
    let status = 'new';
    if (existingSha) status = existingSha === localSha ? 'unchanged' : 'modified';
    return { ...f, status };
  });
}

async function processSingleFile(ctx, buffer, filename) {
  ctx.wizard.state.pendingFiles = [{ filename, content: buffer.toString('utf8'), path: null }];
  await ctx.reply(
    `📄 Received: ${filename} (${format.formatBytes(buffer.length)})\nWhere should this go?`,
    {
      ...Markup.inlineKeyboard([
        [Markup.button.callback('📁 Browse Folders', 'upload:choose:browse')],
        [Markup.button.callback('📍 Root Directory', 'upload:choose:root')],
      ]),
      ...Markup.keyboard([['⌨️ Type Path Instead'], ['❌ Cancel']]).resize(),
    }
  );
  return ctx.wizard.selectStep(2);
}

async function processZip(ctx, buffer) {
  await ctx.reply(`📦 Zip received (${format.formatBytes(buffer.length)}) — extracting...`);

  let zip;
  try {
    zip = new AdmZip(buffer);
  } catch (err) {
    await ctx.reply(format.errorMessage('Upload failed', 'the zip file appears corrupted or empty', 'Re-export the zip and try again.'));
    return;
  }

  const entries = zip.getEntries().filter((e) => !e.isDirectory);
  if (entries.length === 0) {
    await ctx.reply(format.errorMessage('Upload failed', 'the zip contains no files', 'Check the archive and try again.'));
    return;
  }

  // Wrapper detection: if every entry starts with the same single top-level folder, strip it
  const topLevels = new Set(entries.map((e) => e.entryName.split('/')[0]));
  let stripPrefix = '';
  if (topLevels.size === 1) {
    const only = [...topLevels][0];
    if (entries.every((e) => e.entryName.startsWith(`${only}/`))) {
      stripPrefix = `${only}/`;
    }
  }

  const files = entries.map((e) => ({
    path: stripPrefix ? e.entryName.slice(stripPrefix.length) : e.entryName,
    content: e.getData().toString('utf8'),
  }));

  const classified = await classifyFiles(ctx, files);
  if (!classified) return ctx.scene.leave();

  ctx.wizard.state.pendingFiles = classified;
  return showSummary(ctx);
}

async function showSummary(ctx) {
  // Single file needs classification too (was skipped until path was chosen)
  if (ctx.wizard.state.pendingFiles.length === 1 && !ctx.wizard.state.pendingFiles[0].status) {
    const classified = await classifyFiles(ctx, ctx.wizard.state.pendingFiles);
    if (!classified) return ctx.scene.leave();
    ctx.wizard.state.pendingFiles = classified;
  }

  const files = ctx.wizard.state.pendingFiles;
  const counts = { new: 0, modified: 0, unchanged: 0 };
  files.forEach((f) => counts[f.status]++);

  const text =
    `📦 Upload Summary → ${ctx.wizard.state.repoName}\n` +
    `🆕 New: ${counts.new}   ✏️ Modified: ${counts.modified}   ➖ Unchanged: ${counts.unchanged} (skipped)`;

  await ctx.reply('📦 Upload Summary', bbtb.uploadSummary);
  await ctx.reply(text, {
    ...Markup.inlineKeyboard([
      [Markup.button.callback('📋 View File List', 'upload:summary:list')],
      [Markup.button.callback('✅ Commit Changes', 'upload:commit'), Markup.button.callback('❌ Cancel', 'upload:cancel')],
    ]),
  });
  return ctx.wizard.selectStep(3);
}

module.exports = scene;
