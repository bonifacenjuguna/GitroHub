'use strict';

const { InlineKeyboard, InputFile } = require('grammy');
const filesApi = require('../../github/files');
const { formatBytes } = require('../../utils/format');

function enc(s) { return encodeURIComponent(s); }

async function renderFolder(ctx, fullName, folderPath) {
  const [owner, repoName] = fullName.split('/');
  const branch = ctx.session.activeBranch;
  ctx.session.activePath = folderPath;
  const items = await filesApi.listFolder(ctx.from.id, owner, repoName, folderPath, branch);

  let body = `📁 ${fullName} / ${folderPath || '(root)'}\nBranch: ${branch}\n\n`;
  const kb = new InlineKeyboard();
  items.forEach((item) => {
    const icon = item.type === 'dir' ? '📁' : '📄';
    body += `${icon} ${item.name}\n`;
    const targetPath = item.path;
    kb.text(`${icon} ${item.name}`.slice(0, 30), item.type === 'dir'
      ? `repo:${enc(fullName)}:files:${enc(targetPath)}`
      : `file:${enc(fullName)}:${enc(targetPath)}`).row();
  });
  kb.text('📤 Upload Here', `file:upload_here:${enc(fullName)}:${enc(folderPath)}`).row();
  kb.text('🔎 Search Code', `repo:${enc(fullName)}:search`).row();
  const parent = folderPath.split('/').slice(0, -1).join('/');
  kb.text('⬅️ Back', folderPath ? `repo:${enc(fullName)}:files:${enc(parent)}` : `repo:open:${enc(fullName)}`);

  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderFileView(ctx, fullName, filePath) {
  const [owner, repoName] = fullName.split('/');
  const branch = ctx.session.activeBranch;
  const file = await filesApi.getFile(ctx.from.id, owner, repoName, filePath, branch);

  const preview = file.content.length > 500 ? file.content.slice(0, 500) + '\n...' : file.content;
  const body = `📄 ${filePath}\n${fullName} / ${branch}\n${formatBytes(file.size)}\n\n${preview}`;

  const kb = new InlineKeyboard()
    .text('✏️ Edit', `file:${enc(fullName)}:${enc(filePath)}:edit`)
    .text('⬇️ Download', `file:${enc(fullName)}:${enc(filePath)}:download`).row()
    .text('🗑️ Delete', `file:${enc(fullName)}:${enc(filePath)}:delete:confirm`).row()
    .text('⬅️ Back', `repo:${enc(fullName)}:files:${enc(filePath.split('/').slice(0, -1).join('/'))}`);

  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerFiles(bot) {
  bot.callbackQuery(/^repo:(.+):files:(.*)$/, async (ctx) => {
    await renderFolder(ctx, decodeURIComponent(ctx.match[1]), decodeURIComponent(ctx.match[2] || ''));
    await ctx.answerCallbackQuery();
  });

  // NOTE: the more specific :edit / :download / :delete patterns are
  // registered further below and MUST come before the generic file-view
  // matcher, since grammY tries patterns in registration order and the
  // first regex match wins. A generic `/^file:(.+):(.+)$/` here would
  // also match `file:<repo>:<path>:edit` (greedy `.+` swallows the path
  // into group 1, leaving "edit" in group 2), silently breaking those
  // actions. Exact suffix patterns first, generic catch-all last.

  bot.callbackQuery(/^file:upload_here:(.+):(.*)$/, async (ctx) => {
    const { startUploadHere } = require('./upload');
    await startUploadHere(ctx, decodeURIComponent(ctx.match[1]), ctx.session.activeBranch, decodeURIComponent(ctx.match[2]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^file:(.+):(.+):edit$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const filePath = decodeURIComponent(ctx.match[2]);
    const [owner, repoName] = fullName.split('/');
    const file = await filesApi.getFile(ctx.from.id, owner, repoName, filePath, ctx.session.activeBranch);

    if (file.content.length > 2000) {
      const kb = new InlineKeyboard().text('⬇️ Download to Edit Locally', `file:${enc(fullName)}:${enc(filePath)}:download`).text('❌ Cancel', 'flow:cancel');
      await ctx.editOrReply(`✏️ Editing ${filePath} (${formatBytes(file.size)})\n\nToo large to edit inline.`, { reply_markup: kb });
      return ctx.answerCallbackQuery();
    }

    ctx.session.pendingAction = { type: 'edit_file_content', payload: { fullName, filePath, sha: file.sha, branch: ctx.session.activeBranch } };
    const kb = new InlineKeyboard().text('❌ Cancel Edit', 'flow:cancel');
    await ctx.editOrReply(`✏️ Editing ${filePath}\n\nReply with your full edited version.\n\n━━━━━━━━━━\n${file.content}\n━━━━━━━━━━`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^file:(.+):(.+):download$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const filePath = decodeURIComponent(ctx.match[2]);
    const [owner, repoName] = fullName.split('/');
    const file = await filesApi.getFile(ctx.from.id, owner, repoName, filePath, ctx.session.activeBranch);
    await ctx.replyWithDocument(new InputFile(Buffer.from(file.content, 'utf8'), filePath.split('/').pop()));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^file:(.+):(.+):delete:confirm$/, async (ctx) => {
    const fullName = ctx.match[1];
    const filePath = ctx.match[2];
    const kb = new InlineKeyboard().text('✅ Delete', `file:${fullName}:${filePath}:delete:execute`).text('❌ Cancel', `file:${fullName}:${filePath}`);
    await ctx.editOrReply('⚠️ Delete this file? This cannot be undone.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^file:(.+):(.+):delete:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const filePath = decodeURIComponent(ctx.match[2]);
    const [owner, repoName] = fullName.split('/');
    const file = await filesApi.getFile(ctx.from.id, owner, repoName, filePath, ctx.session.activeBranch);
    await filesApi.deleteFile(ctx.from.id, owner, repoName, { path: filePath, branch: ctx.session.activeBranch, message: `Delete ${filePath} via GitroHub`, sha: file.sha });
    await ctx.answerCallbackQuery('Deleted');
    await renderFolder(ctx, fullName, filePath.split('/').slice(0, -1).join('/'));
  });

  // Generic file-view matcher — MUST be last so the specific :edit/:download/
  // :delete patterns above get first refusal on matching callback_data.
  bot.callbackQuery(/^file:(.+):(.+)$/, async (ctx) => {
    await renderFileView(ctx, decodeURIComponent(ctx.match[1]), decodeURIComponent(ctx.match[2]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):download$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    await ctx.answerCallbackQuery('Preparing ZIP...');
    const buffer = await filesApi.downloadZipball(ctx.from.id, owner, repoName, ctx.session.activeBranch);
    await ctx.replyWithDocument(new InputFile(buffer, `${repoName}-${ctx.session.activeBranch}.zip`));
  });
}

module.exports = { registerFiles, renderFolder, renderFileView };
