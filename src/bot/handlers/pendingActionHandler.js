'use strict';

const { InlineKeyboard } = require('grammy');
const branchesApi = require('../../github/branches');
const filesApi = require('../../github/files');
const reposApi = require('../../github/repos');
const { hashPin } = require('../../security/pinLock');
const { setPin } = require('../../db/postgres/users');
const { logAction } = require('../../db/postgres/activityLog');
const { renderBranchList } = require('../menus/branches');
const { renderRepoDetail } = require('../menus/repoDetail');
const { renderSecurityMenu } = require('../menus/security');
const { formatError } = require('../../utils/errors');

function enc(s) { return encodeURIComponent(s); }

/**
 * Handles any plain-text message when ctx.session.pendingAction is set —
 * this is the "waiting for a reply" mechanism used across commit messages,
 * branch names, PIN entry, custom shortcuts, renames, etc. If no
 * pendingAction is set, the message falls through to the URL-detection
 * handler registered after this one.
 */
function registerPendingActionHandler(bot) {
  bot.on('message:text', async (ctx, next) => {
    const pending = ctx.session.pendingAction;
    if (!pending) return next();

    const text = ctx.message.text.trim();
    ctx.session.pendingAction = null; // consume it — one shot per prompt

    try {
      switch (pending.type) {
        case 'create_branch': {
          const { fullName } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          if (!/^[a-zA-Z0-9._/-]+$/.test(text) || text.includes(' ')) {
            await ctx.reply(`❌ Invalid branch name: "${text}"\n\nBranch names can't contain spaces or special characters.`);
            ctx.session.pendingAction = pending;
            return;
          }
          await branchesApi.createBranch(ctx.from.id, owner, repoName, text, ctx.session.activeBranch);
          await ctx.reply(`✅ Branch ${text} created from ${ctx.session.activeBranch}.`);
          await renderBranchList(ctx, fullName);
          return;
        }

        case 'set_pin': {
          if (!/^\d{4}$/.test(text)) {
            await ctx.reply('❌ PIN must be exactly 4 digits. Send 4 digits.');
            ctx.session.pendingAction = pending;
            return;
          }
          await setPin(ctx.from.id, hashPin(text));
          await logAction(ctx.from.id, 'pin_enabled');
          await ctx.reply('✅ PIN Lock enabled. You\'ll be asked for this PIN before destructive actions.');
          await renderSecurityMenu(ctx);
          return;
        }

        case 'edit_description': {
          const { fullName } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          await reposApi.updateRepo(ctx.from.id, owner, repoName, { description: text });
          await ctx.reply('✅ Description updated.');
          await renderRepoDetail(ctx, fullName);
          return;
        }

        case 'edit_topics': {
          const { fullName } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          const topics = text.split(',').map((t) => t.trim().toLowerCase().replace(/\s+/g, '-')).filter(Boolean);
          await reposApi.updateRepo(ctx.from.id, owner, repoName, { topics });
          await ctx.reply('✅ Topics updated.');
          await renderRepoDetail(ctx, fullName);
          return;
        }

        case 'rename_repo': {
          const { fullName } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          const updated = await reposApi.updateRepo(ctx.from.id, owner, repoName, { name: text });
          await logAction(ctx.from.id, 'rename_repo', fullName, { newName: text });
          await ctx.reply(`✅ Renamed to ${updated.full_name}\n🔗 New URL: ${updated.html_url}`);
          await renderRepoDetail(ctx, updated.full_name);
          return;
        }

        case 'homepage_url': {
          const { fullName } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          await reposApi.updateRepo(ctx.from.id, owner, repoName, { homepage: text });
          await ctx.reply('✅ Homepage URL updated.');
          await renderRepoDetail(ctx, fullName);
          return;
        }

        case 'search_repos': {
          const { InlineKeyboard: KB } = require('grammy');
          const all = await reposApi.listRepos(ctx.from.id, { perPage: 100, sort: 'updated' });
          const matches = all.filter((r) => r.name.toLowerCase().includes(text.toLowerCase()));
          let body = `🔍 "${text}" — ${matches.length} matches\n\n`;
          const kb = new KB();
          matches.slice(0, 8).forEach((r, i) => {
            body += `${r.private ? '🔵' : '🟢'} ${r.full_name}\n`;
            kb.text(String(i + 1), `repo:open:${enc(r.full_name)}`);
          });
          kb.row().text('⬅️ Back to Repositories', 'menu:repos');
          await ctx.reply(body, { reply_markup: kb });
          return;
        }

        case 'commit_message': {
          // Generic handoff used by the upload flow — see upload.js for full wiring.
          const { handleCommitMessage } = require('../menus/upload');
          await handleCommitMessage(ctx, pending.payload, text);
          return;
        }

        case 'create_repo_name': {
          const { InlineKeyboard: KB } = require('grammy');
          if (!/^[a-zA-Z0-9._-]+$/.test(text)) {
            await ctx.reply('❌ Invalid repo name. Use letters, numbers, hyphens, underscores, or dots only.');
            ctx.session.pendingAction = pending;
            return;
          }
          const kb = new KB()
            .text('🌐 Public', `repo:create:visibility:public:${encodeURIComponent(text)}`)
            .text('🔒 Private', `repo:create:visibility:private:${encodeURIComponent(text)}`);
          await ctx.reply(`✅ ${text}\n\n🔒 Visibility?`, { reply_markup: kb });
          return;
        }

        case 'import_repo_url': {
          const { InlineKeyboard: KB } = require('grammy');
          const match = text.match(/(?:github\.com\/)?([\w.-]+)\/([\w.-]+?)(?:\.git)?$/);
          if (!match) {
            await ctx.reply('❌ Could not parse that as a GitHub repo. Try owner/name or a full URL.');
            ctx.session.pendingAction = pending;
            return;
          }
          const fullName = `${match[1]}/${match[2]}`;
          const repo = await reposApi.getRepo(ctx.from.id, match[1], match[2]);
          const kb = new KB()
            .text('🍴 Fork to My Account', `repo:import:fork:${enc(fullName)}`).row()
            .text('❌ Cancel', 'flow:cancel');
          await ctx.reply(`📦 ${repo.full_name}\n⭐ ${repo.stargazers_count} · 🍴 ${repo.forks_count}\n\n"${repo.description || ''}"`, { reply_markup: kb });
          return;
        }

        case 'create_pr_title': {
          const { fullName, head } = pending.payload;
          ctx.session.pendingAction = { type: 'create_pr_body', payload: { fullName, head, title: text } };
          await ctx.reply('📝 Send a description for this PR, or send "skip".');
          return;
        }

        case 'create_pr_body': {
          const prApi = require('../../github/pullRequests');
          const { fullName, head, title } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          const repo = await reposApi.getRepo(ctx.from.id, owner, repoName);
          const pr = await prApi.createPull(ctx.from.id, owner, repoName, {
            title, head, base: repo.default_branch, body: text === 'skip' ? '' : text,
          });
          await ctx.reply(`✅ PR #${pr.number} created: ${pr.html_url}`);
          return;
        }

        case 'create_issue_title': {
          const { fullName } = pending.payload;
          ctx.session.pendingAction = { type: 'create_issue_body', payload: { fullName, title: text } };
          await ctx.reply('📝 Send a description, or send "skip".');
          return;
        }

        case 'create_issue_body': {
          const issuesApi = require('../../github/issues');
          const { fullName, title } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          const issue = await issuesApi.createIssue(ctx.from.id, owner, repoName, { title, body: text === 'skip' ? '' : text });
          await ctx.reply(`✅ Issue #${issue.number} created: ${issue.html_url}`);
          return;
        }

        case 'issue_comment': {
          const issuesApi = require('../../github/issues');
          const { fullName, number } = pending.payload;
          await issuesApi.addComment(ctx.from.id, ...fullName.split('/'), number, text);
          await ctx.reply('✅ Comment added.');
          return;
        }

        case 'create_release_tag': {
          const { fullName } = pending.payload;
          ctx.session.pendingAction = { type: 'create_release_notes', payload: { fullName, tag: text } };
          await ctx.reply('📝 Send release notes, or send "auto" to generate from commits.');
          return;
        }

        case 'create_release_notes': {
          const releasesApi = require('../../github/releases');
          const { fullName, tag } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          let body = text;
          if (text.toLowerCase() === 'auto') {
            const generated = await releasesApi.generateReleaseNotes(ctx.from.id, owner, repoName, tag);
            body = generated.body;
          }
          const release = await releasesApi.createRelease(ctx.from.id, owner, repoName, {
            tagName: tag, targetCommitish: ctx.session.activeBranch, name: tag, body,
          });
          await ctx.reply(`🚀 Released ${release.tag_name}: ${release.html_url}`);
          return;
        }

        case 'search_code_global': {
          const { InlineKeyboard: KB } = require('grammy');
          const results = await filesApi.searchCodeGlobal(ctx.from.id, text);
          let body = `🔍 "${text}" — ${results.length} matches\n\n`;
          results.slice(0, 8).forEach((r) => (body += `📄 ${r.repository.full_name}: ${r.path}\n`));
          await ctx.reply(body || 'No matches found.');
          return;
        }

        case 'search_code_repo': {
          const { fullName } = pending.payload;
          const results = await filesApi.searchCodeInRepo(ctx.from.id, ...fullName.split('/'), text);
          let body = `🔍 "${text}" in ${fullName} — ${results.length} matches\n\n`;
          results.slice(0, 8).forEach((r) => (body += `📄 ${r.path}\n`));
          await ctx.reply(body || 'No matches found.');
          return;
        }

        case 'search_users': {
          const octokit = await require('../../github/client').getClient(ctx.from.id);
          const { data } = await octokit.rest.search.users({ q: text });
          let body = `🔍 "${text}" — ${data.total_count} matches\n\n`;
          data.items.slice(0, 5).forEach((u) => (body += `👤 ${u.login} — ${u.html_url}\n`));
          await ctx.reply(body || 'No matches found.');
          return;
        }

        case 'search_orgs': {
          const octokit = await require('../../github/client').getClient(ctx.from.id);
          const { data } = await octokit.rest.search.users({ q: `${text} type:org` });
          let body = `🔍 "${text}" — ${data.total_count} matches\n\n`;
          data.items.slice(0, 5).forEach((o) => (body += `🏢 ${o.login} — ${o.html_url}\n`));
          await ctx.reply(body || 'No matches found.');
          return;
        }

        case 'edit_file_content': {
          const { fullName, filePath, sha, branch } = pending.payload;
          const [owner, repoName] = fullName.split('/');
          await filesApi.commitFile(ctx.from.id, owner, repoName, {
            path: filePath, branch, content: text, message: `Update ${filePath} via GitroHub`, existingSha: sha,
          });
          await ctx.reply(`✅ ${filePath} updated.`);
          return;
        }

        case 'api_explorer': {
          const octokit = await require('../../github/client').getClient(ctx.from.id);
          try {
            const { data } = await octokit.request(`GET ${text}`);
            const json = JSON.stringify(data, null, 2).slice(0, 3500);
            await ctx.reply('```json\n' + json + '\n```', { parse_mode: 'MarkdownV2' }).catch(() => ctx.reply(json));
          } catch (err) {
            await ctx.reply(`❌ Request failed: ${err.message}`);
          }
          return;
        }

        case 'create_gist_filename': {
          ctx.session.pendingAction = { type: 'create_gist_content', payload: { filename: text } };
          await ctx.reply('📋 Send the code/content for this gist.');
          return;
        }

        case 'create_gist_content': {
          const octokit = await require('../../github/client').getClient(ctx.from.id);
          const { filename } = pending.payload;
          const { data } = await octokit.rest.gists.create({
            files: { [filename]: { content: text } }, public: false,
          });
          await ctx.reply(`✅ Gist created: ${data.html_url}`);
          return;
        }

        default: {
          await ctx.reply('⚠️ That input was not expected right now. Use /menu to start fresh.');
          return;
        }
      }
    } catch (err) {
      const formatted = formatError(err, { backCallback: 'menu:main' });
      const kb = new InlineKeyboard();
      formatted.buttons.forEach((row) => { kb.row(); row.forEach((b) => kb.text(b.text, b.data)); });
      await ctx.reply(formatted.text, { reply_markup: kb });
    }
  });
}

module.exports = { registerPendingActionHandler };
