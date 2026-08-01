'use strict';

const { InlineKeyboard } = require('grammy');
const releasesApi = require('../../github/releases');
const { relativeTime } = require('../../utils/format');

function enc(s) { return encodeURIComponent(s); }

async function renderReleaseList(ctx, fullName) {
  const [owner, repoName] = fullName.split('/');
  const releases = await releasesApi.listReleases(ctx.from.id, owner, repoName);
  let body = `🚀 Releases — ${fullName} (${releases.length} total)\n\n`;
  const kb = new InlineKeyboard();
  releases.slice(0, 6).forEach((r, i) => {
    body += `🏷️ ${r.tag_name}${i === 0 ? ' (latest)' : ''}\n   📅 ${relativeTime(r.published_at)}\n   "${r.name || r.tag_name}"\n\n`;
    kb.text(String(i + 1), `release:${enc(fullName)}:${r.id}`);
  });
  kb.row().text('➕ Create Release', `release:${enc(fullName)}:create`).row();
  kb.text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerReleases(bot) {
  bot.callbackQuery(/^repo:(.+):releases$/, async (ctx) => {
    await renderReleaseList(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^release:(.+):(\d+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const release = await releasesApi.getRelease(ctx.from.id, ...fullName.split('/'), ctx.match[2]);
    let body = `🏷️ ${release.tag_name}\n📅 ${relativeTime(release.published_at)}\n\n${release.body ? release.body.slice(0, 400) : ''}`;
    const kb = new InlineKeyboard()
      .text('🗑️ Delete Release', `release:${enc(fullName)}:${release.id}:delete:confirm`).row()
      .text('⬅️ Back to Releases', `repo:${enc(fullName)}:releases`);
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^release:(.+):create$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'create_release_tag', payload: { fullName } };
    await ctx.editOrReply('🏷️ Create New Release\n\nSend a tag name (e.g. v1.0.1).', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^release:(.+):(\d+):delete:confirm$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const kb = new InlineKeyboard().text('✅ Delete', `release:${enc(fullName)}:${ctx.match[2]}:delete:execute`).text('❌ Cancel', `release:${enc(fullName)}:${ctx.match[2]}`);
    await ctx.editOrReply('⚠️ Delete this release? The git tag itself is not removed.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^release:(.+):(\d+):delete:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await releasesApi.deleteRelease(ctx.from.id, ...fullName.split('/'), ctx.match[2]);
    await ctx.answerCallbackQuery('Deleted');
    await renderReleaseList(ctx, fullName);
  });
}

module.exports = { registerReleases, renderReleaseList };
