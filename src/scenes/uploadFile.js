const { Scenes, Markup } = require('telegraf');
const AdmZip = require('adm-zip');
const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const { gitBlobSha } = require('../lib/gitHash');
const config = require('../config');
const { listDirectory } = require('../handlers/browseFiles');

const PATH_EXAMPLES =
  'Examples:\n' +
  '• src/index.js\n' +
  '• assets/images/logo.png\n' +
  '• config/settings.json';

const typePathBbtb = Markup.keyboard([
  ['📍 Use Root', '⬅️ Back'],
  ['❌ Cancel'],
]).resize();

const scene = new Scenes.WizardScene(
  'uploadFile',

  // Step 0 — entry
  async (ctx) => {
    ctx.wizard.state.repoName = ctx.wizard.state.repoName || ctx.scene.state.repoName;
    await ctx.reply(
      `📤 Send a file or a .zip (max ${format.formatBytes(config.MAX_ZIP_SIZE_BYTES)}) to upload to ${ctx.wizard.state.repoName}\n\n` +
      `⚠️ Send it as a document/file attachment (📎 icon → File) — not via the photo/gallery picker, which compresses images and would alter the file's bytes.`,
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

    if (ctx.message && ctx.message.photo) {
      await ctx.reply(format.errorMessage(
        'Can\u2019t upload this file',
        'it was sent as a compressed photo, not a file attachment — Telegram compresses images sent via the photo picker, which alters the original bytes',
        'Use the 📎 attachment icon and choose "File" (not "Photo/Gallery") to send it unmodified, or ❌ Cancel.'
      ));
      return;
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
      await ctx.reply(`⌨️ Type the destination path.\n\n${PATH_EXAMPLES}\n\nOr tap 📍 Use Root below.`, typePathBbtb);
      return;
    }
    if (ctx.message && ctx.message.text === '📍 Use Root') {
      ctx.wizard.state.pendingFiles[0].path = ctx.wizard.state.pendingFiles[0].filename;
      return showSummary(ctx);
    }
    if (ctx.message && ctx.message.text === '⬅️ Back') {
      return processSingleFile(ctx, null, null, true);
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
          `${PATH_EXAMPLES}\n\nTry again, or tap 📍 Use Root below.`
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
        .map((f) => `${statusIcon(f.status)} ${f.path}${f.status === 'modified' ? ` (${f.oldSize} → ${f.newSize})` : ''}`)
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
        await ctx.reply('➖ Nothing to commit — every file matches what\u2019s already in the repo.', bbtb.mainMenu);
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

  return Promise.all(files.map(async (f) => {
    const existingSha = existingByPath.get(f.path);
    const localSha = gitBlobSha(f.content);
    let status = 'new';
    let oldSize;
    if (existingSha) {
      status = existingSha === localSha ? 'unchanged' : 'modified';
      if (status === 'modified') {
        try {
          const existing = await github.getFileContent(token, user.login, ctx.wizard.state.repoName, f.path);
          oldSize = format.formatBytes(existing.size);
        } catch (_) { /* best-effort */ }
      }
    }
    return { ...f, status, oldSize, newSize: format.formatBytes(Buffer.byteLength(f.content)) };
  }));
}

async function processSingleFile(ctx, buffer, filename, isBackNav = false) {
  if (!isBackNav) {
    ctx.wizard.state.pendingFiles = [{ filename, content: buffer.toString('utf8'), path: null }];
    delete ctx.wizard.state.pendingFiles[0].status;
  }

  // Show existing top-level repo structure for context before asking where to put it
  const token = await requireConnected(ctx);
  if (!token) return ctx.scene.leave();

  let structureLine = '';
  try {
    const user = await github.getAuthenticatedUser(token);
    const tree = await github.getTree(token, user.login, ctx.wizard.state.repoName);
    const topLevel = listDirectory(tree, '');
    if (topLevel.length > 0) {
      const preview = topLevel.slice(0, 8).map((e) => (e.type === 'tree' ? `📁 ${e.name}/` : `📄 ${e.name}`)).join('\n');
      structureLine = `\n\n📂 Current top-level contents:\n${preview}${topLevel.length > 8 ? `\n… and ${topLevel.length - 8} more` : ''}`;
    } else {
      structureLine = '\n\n📂 This repo is currently empty.';
    }
  } catch (_) { /* best-effort — don't block the flow if this fails */ }

  const f = ctx.wizard.state.pendingFiles[0];
  await ctx.reply(
    `📄 Received: ${f.filename} (${format.formatBytes(Buffer.byteLength(f.content, 'utf8'))})\nWhere should this go?${structureLine}`,
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

  await ctx.reply('📦 Upload Summary', bbtb.uploadSummary);

  // Nothing changed at all — refuse outright, per design, rather than
  // offering a Commit button that would push an empty no-op commit.
  if (counts.new === 0 && counts.modified === 0) {
    const names = files.map((f) => f.path).join(', ');
    await ctx.reply(
      `📦 Upload Summary → ${ctx.wizard.state.repoName}\n` +
      `➖ No changes detected — ${files.length === 1 ? `"${names}" matches` : `all ${files.length} files match`} what's already in the repo.\n\n` +
      `Nothing to upload.`,
      Markup.inlineKeyboard([[Markup.button.callback('📦 Open Repo', `repo:${ctx.wizard.state.repoName}`)]])
    );
    return ctx.scene.leave();
  }

  const changeDetail = files
    .filter((f) => f.status === 'modified')
    .slice(0, 3)
    .map((f) => `✏️ ${f.path}: ${f.oldSize || '?'} → ${f.newSize}`)
    .join('\n');

  const text =
    `📦 Upload Summary → ${ctx.wizard.state.repoName}\n` +
    `🆕 New: ${counts.new}   ✏️ Modified: ${counts.modified}   ➖ Unchanged: ${counts.unchanged} (skipped)` +
    (changeDetail ? `\n\n${changeDetail}` : '');

  await ctx.reply(text, {
    ...Markup.inlineKeyboard([
      [Markup.button.callback('📋 View File List', 'upload:summary:list')],
      [Markup.button.callback('✅ Commit Changes', 'upload:commit'), Markup.button.callback('❌ Cancel', 'upload:cancel')],
    ]),
  });
  return ctx.wizard.selectStep(3);
}

module.exports = scene;
