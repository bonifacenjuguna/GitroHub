const { Scenes, Markup } = require('telegraf');
const style = require('../keyboards/buttonStyle');
const github = require('../lib/github');
const repoCache = require('../lib/repoCache');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const { gitBlobSha } = require('../lib/gitHash');
const config = require('../config');
const { listDirectory } = require('../handlers/browseFiles');
const pathMemory = require('../lib/pathMemory');
const fileBufferCache = require('../lib/fileBufferCache');
const ephemeral = require('../lib/ephemeral');

const PATH_EXAMPLES =
  'Examples:\n' +
  '• src/index.js\n' +
  '• assets/images/logo.png\n' +
  '• config/settings.json';

const typePathBbtb = Markup.keyboard([
  ['📍 Use Root', '⬅️ Back'],
  ['❌ Cancel'],
]).resize();

/** Releases every cached file buffer for this wizard session — call at every exit point. */
function releasePendingFiles(ctx) {
  const files = ctx.wizard.state.pendingFiles;
  if (files) fileBufferCache.releaseAll(files.map((f) => f.contentRef).filter(Boolean));
  if (ctx.wizard.state.pendingZipRef) fileBufferCache.release(ctx.wizard.state.pendingZipRef);
}

/** Exposed so bot.js's global scene-escape handler can clean up cached
 * buffers even when the person leaves via a nav button instead of Cancel. */
function releaseOnExternalLeave(ctx) {
  if (ctx.wizard && ctx.wizard.state) releasePendingFiles(ctx);
}

const scene = new Scenes.WizardScene(
  'uploadFile',

  async (ctx) => {
    const state = ctx.scene.state || {};
    ctx.wizard.state.repoName = ctx.wizard.state.repoName || state.repoName;
    ctx.wizard.state.presetDir = state.presetDir;
    ctx.wizard.state.suggestedDir = state.suggestedDir;
    ctx.wizard.state.lockedPath = state.lockedPath;
    ctx.wizard.state.mode = state.mode || 'upload';

    if (ctx.wizard.state.mode === 'replaceFolder' && !ctx.wizard.state.syncConfirmed) {
      const dirLabel = ctx.wizard.state.presetDir || '(root)';
      await ctx.reply(
        `🔁 Replace ${dirLabel}\n` +
        `This makes the folder match exactly what you upload next:\n` +
        `• Files you send will be added or updated\n` +
        `• Any file already here that you DON'T include will be deleted\n\n` +
        `⚠️ This is a full sync, not a normal upload.`,
        Markup.inlineKeyboard([
          [style.callback('Understood, Continue', 'upload:sync:continue', style.GREEN)],
          [style.callback('❌ Cancel', 'upload:sync:cancel', style.RED)],
        ])
      );
      // Advance the wizard cursor to the step that actually handles the
      // button tap (below). Without this, Telegraf re-runs THIS step on the
      // next update, sees syncConfirmed still false, and resends this same
      // message forever — regardless of which button was tapped.
      return ctx.wizard.selectStep(1);
    }

    return promptForFile(ctx);
  },

  async (ctx) => {
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:sync:continue') {
      await ctx.answerCbQuery();
      ctx.wizard.state.syncConfirmed = true;
      return promptForFile(ctx);
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:sync:cancel') {
      await ctx.answerCbQuery();
      await ephemeral.sendEphemeral(ctx, 'Cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }

    if (ctx.message && ctx.message.text === '❌ Cancel') {
      releasePendingFiles(ctx);
      await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }

    // 🔒 Password-protected zip — this step re-enters itself waiting for a
    // password reply rather than advancing, since we're still logically
    // "receiving the file" until extraction actually succeeds.
    if (ctx.wizard.state.awaitingZipPassword) {
      if (!ctx.message || !ctx.message.text) {
        await ctx.reply('Send the zip password as text, or ❌ Cancel.');
        return;
      }
      const password = ctx.message.text.trim();
      const buffer = fileBufferCache.get(ctx.wizard.state.pendingZipRef);
      delete ctx.wizard.state.awaitingZipPassword;
      if (!buffer) {
        // Cache entry expired (session sat idle past the TTL) — nothing to retry with.
        delete ctx.wizard.state.pendingZipRef;
        await ctx.reply(format.errorMessage('Upload failed', 'the file expired while waiting for a password', 'Please resend the zip.'));
        return promptForFile(ctx);
      }
      return processZip(ctx, buffer, password);
    }

    // 📦 Extract vs upload-as-is — asked BEFORE downloading, since which
    // size limit applies depends on the answer (extracting uses the small
    // archive limit; "as-is" is really just a single file at that point,
    // so it gets the larger single-file limit instead).
    if (ctx.wizard.state.pendingArchiveDoc) {
      const pending = ctx.wizard.state.pendingArchiveDoc;

      if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:archive:cancel') {
        await ctx.answerCbQuery();
        delete ctx.wizard.state.pendingArchiveDoc;
        releasePendingFiles(ctx);
        await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
        return ctx.scene.leave();
      }

      if (ctx.callbackQuery && (ctx.callbackQuery.data === 'upload:archive:extract' || ctx.callbackQuery.data === 'upload:archive:asis')) {
        await ctx.answerCbQuery();
        const choice = ctx.callbackQuery.data.split('upload:archive:')[1];
        delete ctx.wizard.state.pendingArchiveDoc;

        const sizeLimit = choice === 'extract' ? config.MAX_ZIP_SIZE_BYTES : config.MAX_SINGLE_FILE_BYTES;
        if (pending.fileSize > sizeLimit) {
          await ctx.reply(format.errorMessage(
            choice === 'extract' ? 'Archive exceeds size limit' : 'File exceeds size limit',
            `${pending.fileName} is ${format.formatBytes(pending.fileSize)}, limit is ${format.formatBytes(sizeLimit)}`,
            choice === 'extract' ? 'Please split or compress further, then resend.' : 'Keep it under the single-file limit, then resend.'
          ));
          return promptForFile(ctx);
        }

        const fileLink = await ctx.telegram.getFileLink(pending.fileId);
        let res;
        try {
          res = await fetch(fileLink.href, { signal: AbortSignal.timeout(20000) });
        } catch (err) {
          await ctx.reply(format.errorMessage(
            'Upload failed',
            err.name === 'TimeoutError' ? 'downloading the file from Telegram took too long' : err.message,
            'Try again.'
          ));
          return promptForFile(ctx);
        }
        const buffer = Buffer.from(await res.arrayBuffer());

        if (choice === 'asis') return processSingleFile(ctx, buffer, pending.fileName, pending.fileId);
        if (pending.isZip) return processZip(ctx, buffer);
        return processTar(ctx, buffer, pending.isTarGz);
      }

      // Anything else while this choice is pending — re-prompt rather than
      // silently processing a new message on top of a stale pending doc.
      await ctx.reply('Please tap 📦 Extract Contents, 📁 Upload As\u2011Is, or ❌ Cancel above.');
      return;
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
    const lowerName = doc.file_name.toLowerCase();

    const isZip = lowerName.endsWith('.zip');
    const isTarGz = lowerName.endsWith('.tar.gz') || lowerName.endsWith('.tgz');
    const isTar = !isTarGz && lowerName.endsWith('.tar');
    const isArchive = isZip || isTar || isTarGz;

    if (isArchive) {
      ctx.wizard.state.pendingArchiveDoc = {
        fileId: doc.file_id, fileName: doc.file_name, fileSize: doc.file_size, isZip, isTarGz,
      };
      await ctx.reply(
        `📦 ${doc.file_name} (${format.formatBytes(doc.file_size)}) — how should this be uploaded?`,
        Markup.inlineKeyboard([
          [style.callback('📦 Extract Contents', 'upload:archive:extract')],
          [style.callback('📁 Upload As-Is (single file)', 'upload:archive:asis')],
          [style.callback('❌ Cancel', 'upload:archive:cancel')],
        ])
      );
      return;
    }

    // Anything that isn't .zip/.tar/.tar.gz — including .rar/.7z and
    // anything else — is just an opaque single file as far as GitroHub is
    // concerned. It was never able to extract RAR/7z anyway, so there's no
    // reason to refuse them outright instead of storing them as-is, same
    // as a .pdf or .png.
    if (doc.file_size > config.MAX_SINGLE_FILE_BYTES) {
      await ctx.reply(format.errorMessage(
        'File exceeds size limit',
        `${doc.file_name} is ${format.formatBytes(doc.file_size)}, limit is ${format.formatBytes(config.MAX_SINGLE_FILE_BYTES)}`,
        'For larger files, zip them first (as an archive to extract, up to 1MB compressed), then resend.'
      ));
      return;
    }

    const fileLink = await ctx.telegram.getFileLink(doc.file_id);
    let res;
    try {
      res = await fetch(fileLink.href, { signal: AbortSignal.timeout(20000) });
    } catch (err) {
      await ctx.reply(format.errorMessage(
        'Upload failed',
        err.name === 'TimeoutError' ? 'downloading the file from Telegram took too long' : err.message,
        'Try again.'
      ));
      return;
    }
    const buffer = Buffer.from(await res.arrayBuffer());
    return processSingleFile(ctx, buffer, doc.file_name, doc.file_id);
  },

  async (ctx) => {
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:choose:root') {
      await ctx.answerCbQuery();
      ctx.wizard.state.pendingFiles[0].path = ctx.wizard.state.pendingFiles[0].filename;
      return showSummary(ctx);
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:choose:suggested') {
      await ctx.answerCbQuery();
      const dir = ctx.wizard.state.suggestedDir;
      ctx.wizard.state.pendingFiles[0].path = dir ? `${dir}/${ctx.wizard.state.pendingFiles[0].filename}` : ctx.wizard.state.pendingFiles[0].filename;
      return showSummary(ctx);
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:choose:default') {
      await ctx.answerCbQuery();
      const defaultsLib = require('../lib/defaults');
      const d = await defaultsLib.getDefaults(ctx.from.id);
      const dir = d ? d.default_upload_path : '';
      ctx.wizard.state.pendingFiles[0].path = dir ? `${dir}/${ctx.wizard.state.pendingFiles[0].filename}` : ctx.wizard.state.pendingFiles[0].filename;
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
      return processSingleFile(ctx, null, null, null, true);
    }
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      releasePendingFiles(ctx);
      await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
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

  async (ctx) => {
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:summary:list') {
      await ctx.answerCbQuery();
      const list = ctx.wizard.state.pendingFiles
        .map((f) => `${statusIcon(f.status)} ${f.path}${f.status === 'modified' ? ` (${f.oldSize} → ${f.newSize})` : ''}`)
        .join('\n');
      const toDelete = ctx.wizard.state.toDelete || [];
      const delList = toDelete.length ? `\n\n🗑 Will be REMOVED:\n${toDelete.join('\n')}` : '';
      await ctx.reply(`📋 Files:\n${list}${delList}`);
      return;
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:cancel') {
      await ctx.answerCbQuery();
      releasePendingFiles(ctx);
      await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:commit') {
      await ctx.answerCbQuery();
      const changed = ctx.wizard.state.pendingFiles.filter((f) => f.status !== 'unchanged');
      const toDelete = ctx.wizard.state.toDelete || [];
      if (changed.length === 0 && toDelete.length === 0) {
        releasePendingFiles(ctx);
        await ephemeral.sendEphemeral(ctx, '➖ Nothing to commit — every file matches what\u2019s already in the repo.', bbtb.mainMenu);
        return ctx.scene.leave();
      }
      await ephemeral.sendEphemeral(ctx, 'Write a commit message, use default, or tap a suggestion:', bbtb.cancelWithSkip);
      // Quick-tap common commit messages instead of always typing one.
      // Colorless: these are value picks, not navigation.
      await ctx.reply(
        'Suggestions:',
        Markup.inlineKeyboard([
          [style.callback('🐛 Fix bug', 'upload:msgpick:Fix bug')],
          [style.callback('📝 Update README', 'upload:msgpick:Update README')],
          [style.callback('✨ Initial commit', 'upload:msgpick:Initial commit')],
          [style.callback('🔧 Minor changes', 'upload:msgpick:Minor changes')],
        ])
      );
      return ctx.wizard.next();
    }
    await ctx.reply('Tap 📋 View File List, ✅ Commit Changes, or ❌ Cancel above.');
  },

  async (ctx) => {
    // 📅 Schedule for Later — custom date/time text, after "⌨️ Custom" was tapped.
    if (ctx.wizard.state.awaitingUploadScheduleTime) {
      if (ctx.message && ctx.message.text === '❌ Cancel') {
        delete ctx.wizard.state.awaitingUploadScheduleTime;
        releasePendingFiles(ctx);
        await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
        return ctx.scene.leave();
      }
      if (!ctx.message || !ctx.message.text) {
        await ctx.reply('Send the date and time as text, or ❌ Cancel.');
        return;
      }
      const users = require('../lib/users');
      const timezone = require('../lib/timezone');
      const user = await users.getUser(ctx.from.id);
      const tz = user.timezone || 'UTC';
      const scheduledFor = timezone.parseFlexibleDateTime(ctx.message.text.trim(), tz);
      if (!scheduledFor) {
        await ctx.reply(format.errorMessage('Couldn\u2019t read that', 'try "14:00", "12-25 09:00", or "2026-09-15 14:00"', '12-hour like "2:30pm" also works, or ❌ Cancel.'));
        return;
      }
      if (scheduledFor.getTime() <= Date.now()) {
        await ctx.reply(format.errorMessage('That time has already passed', `that resolves to the past in ${tz}`, 'Send a future date/time, or ❌ Cancel.'));
        return;
      }
      delete ctx.wizard.state.awaitingUploadScheduleTime;
      return finalizeUploadSchedule(ctx, scheduledFor, tz);
    }

    // 📅 Schedule for Later — quick-pick shown after "📅 Schedule for Later" was tapped.
    if (ctx.wizard.state.awaitingUploadSchedulePick) {
      if (!ctx.callbackQuery || !ctx.callbackQuery.data.startsWith('upload:schedulepick:')) {
        await ctx.reply('Tap a time option above, or ❌ Cancel.');
        return;
      }
      await ctx.answerCbQuery();
      const pick = ctx.callbackQuery.data.split('upload:schedulepick:')[1];
      const users = require('../lib/users');
      const user = await users.getUser(ctx.from.id);
      const tz = user.timezone || 'UTC';

      if (pick === 'custom') {
        delete ctx.wizard.state.awaitingUploadSchedulePick;
        ctx.wizard.state.awaitingUploadScheduleTime = true;
        await ephemeral.sendEphemeral(
          ctx,
          `⌨️ Send a time in your timezone (${tz} — change it in 🤖 Automation → 🌍 Timezone) — just "14:00" works (today, or tomorrow if that's already passed), or add a date: "12-25 09:00", or the full "2026-09-15 14:00" if you want to be exact. 12-hour like "2:30pm" also works.`,
          bbtb.cancelOnly
        );
        return;
      }

      delete ctx.wizard.state.awaitingUploadSchedulePick;
      const now = new Date();
      let scheduledFor;
      if (pick === '1h') scheduledFor = new Date(now.getTime() + 60 * 60 * 1000);
      else if (pick === '3days') scheduledFor = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);
      else if (pick === 'tomorrow9am') {
        const timezone = require('../lib/timezone');
        const todayLocal = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
        const [ty, tm, td] = todayLocal.split('-').map(Number);
        const tomorrowLocal = new Date(Date.UTC(ty, tm - 1, td + 1));
        const y = tomorrowLocal.getUTCFullYear();
        const mo = String(tomorrowLocal.getUTCMonth() + 1).padStart(2, '0');
        const d = String(tomorrowLocal.getUTCDate()).padStart(2, '0');
        scheduledFor = timezone.zonedTimeToUtc(`${y}-${mo}-${d}`, '09:00', tz);
        if (scheduledFor.getTime() <= now.getTime()) scheduledFor = new Date(scheduledFor.getTime() + 24 * 60 * 60 * 1000);
      }
      return finalizeUploadSchedule(ctx, scheduledFor, tz);
    }

    // ✅ Commit Now vs 📅 Schedule for Later — shown after the commit
    // message is already decided, only when this upload is eligible for
    // scheduling at all (see the eligibility check further down).
    if (ctx.wizard.state.awaitingUploadNowOrLater) {
      if (ctx.message && ctx.message.text === '❌ Cancel') {
        delete ctx.wizard.state.awaitingUploadNowOrLater;
        releasePendingFiles(ctx);
        await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
        return ctx.scene.leave();
      }
      if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:schedulelater') {
        await ctx.answerCbQuery();
        delete ctx.wizard.state.awaitingUploadNowOrLater;
        ctx.wizard.state.awaitingUploadSchedulePick = true;
        await ctx.reply('📅 When should this be uploaded?', Markup.inlineKeyboard([
          [style.callback('In 1 hour', 'upload:schedulepick:1h')],
          [style.callback('In 3 days', 'upload:schedulepick:3days')],
          [style.callback('Tomorrow 9am', 'upload:schedulepick:tomorrow9am')],
          [style.callback('⌨️ Custom date/time', 'upload:schedulepick:custom')],
        ]));
        return;
      }
      if (ctx.callbackQuery && ctx.callbackQuery.data === 'upload:committnow') {
        await ctx.answerCbQuery();
        delete ctx.wizard.state.awaitingUploadNowOrLater;
        return commitPendingUpload(ctx, ctx.wizard.state.pendingCommitMessage);
      }
      await ctx.reply('Tap ✅ Commit Now, 📅 Schedule for Later, or ❌ Cancel above.');
      return;
    }

    const defaultsLib = require('../lib/defaults');
    const d = await defaultsLib.getDefaults(ctx.from.id);
    let message = ctx.wizard.state.mode === 'replaceFolder'
      ? 'Sync via GitroHub'
      : (d && d.default_commit_message) || 'Update via GitroHub';
    if (ctx.message && ctx.message.text === '❌ Cancel') {
      releasePendingFiles(ctx);
      await ephemeral.sendEphemeral(ctx, 'Upload cancelled.', bbtb.mainMenu);
      return ctx.scene.leave();
    }
    if (ctx.callbackQuery && ctx.callbackQuery.data.startsWith('upload:msgpick:')) {
      await ctx.answerCbQuery();
      message = ctx.callbackQuery.data.split('upload:msgpick:')[1];
    } else if (ctx.message && ctx.message.text && ctx.message.text !== '⏭️ Skip') {
      message = ctx.message.text.trim();
    } else if (!(ctx.message && ctx.message.text === '⏭️ Skip')) {
      await ctx.reply('Send a commit message, tap a suggestion, tap ⏭️ Skip for default, or ❌ Cancel.');
      return;
    }

    // 📅 Scheduling only makes sense for a single, self-contained file —
    // a multi-file directory sync (or one that also deletes files) needs
    // to compare against the repo's LIVE state, which could well have
    // changed by the time a schedule fires; replaying a stale diff later
    // would be a correctness problem, not a convenience. So the Now/Later
    // choice is only offered here — everything else commits immediately,
    // exactly as it always has.
    const changed = ctx.wizard.state.pendingFiles.filter((f) => f.status !== 'unchanged');
    const toDelete = ctx.wizard.state.toDelete || [];
    const eligibleForScheduling = changed.length === 1 && toDelete.length === 0 && changed[0].fileId;

    if (eligibleForScheduling) {
      ctx.wizard.state.pendingCommitMessage = message;
      ctx.wizard.state.awaitingUploadNowOrLater = true;
      await ctx.reply(
        `📤 Ready to upload "${changed[0].path}" to ${ctx.wizard.state.repoName}\nCommit: "${message}"`,
        Markup.inlineKeyboard([
          [style.callback('✅ Commit Now', 'upload:committnow'), style.callback('📅 Schedule for Later', 'upload:schedulelater')],
        ])
      );
      return;
    }

    return commitPendingUpload(ctx, message);
  }
);

/** The actual commit — split out from the step above so both the
 * immediate-commit path and the "✅ Commit Now" tap (after having shown
 * the Now/Later choice) can call the exact same code, rather than two
 * near-duplicate copies of this logic drifting apart over time. */
async function commitPendingUpload(ctx, message) {
    const token = await requireConnected(ctx);
    if (!token) return ctx.scene.leave();

    const changed = ctx.wizard.state.pendingFiles.filter((f) => f.status !== 'unchanged');
    const toDelete = ctx.wizard.state.toDelete || [];
    const actionLock = require('../lib/actionLock');
    const { skipped } = await actionLock.withLock(ctx.from.id, 'uploadCommit', async () => {
    try {
      const user = await repoCache.getUser(ctx.from.id, token);
      await github.commitMultipleFiles(
        token,
        user.login,
        ctx.wizard.state.repoName,
        changed.map((f) => ({ path: f.path, content: fileBufferCache.get(f.contentRef) })),
        message,
        toDelete
      );
      repoCache.invalidateRepos(ctx.from.id);
      repoCache.invalidateLanguages(ctx.from.id, ctx.wizard.state.repoName);
      repoCache.invalidateTreeStats(ctx.from.id, ctx.wizard.state.repoName);
      await activity.log(
        ctx.from.id,
        '⬆️',
        `${ctx.wizard.state.mode === 'replaceFolder' ? 'Synced' : 'Uploaded'} ${changed.length} file(s)${toDelete.length ? `, removed ${toDelete.length}` : ''} → ${ctx.wizard.state.repoName}`
      );

      if (changed.length > 0) {
        const dir = changed[0].path.split('/').slice(0, -1).join('/');
        await pathMemory.setLastPath(ctx.from.id, ctx.wizard.state.repoName, dir);
        // Feeds the global "learned default upload path" suggestion
        // (lib/defaults.checkUploadPathPattern), separate from this
        // per-repo memory.
        const defaultsLib = require('../lib/defaults');
        await defaultsLib.bumpUploadPathFrequency(ctx.from.id, dir).catch(() => {});
      }

      let summary = `✅ Pushed ${changed.length} changes to ${ctx.wizard.state.repoName}`;
      if (toDelete.length) summary += `, removed ${toDelete.length}`;
      summary += `\nCommit: "${message}"`;

      const bulkActions = require('../handlers/bulkActions');
      await bulkActions.maybeAddLongOpNotice(ctx, changed.length + toDelete.length, { label: 'files' });
      await ctx.reply(summary, bbtb.mainMenu);
    } catch (err) {
      await activity.log(ctx.from.id, '⚠️', `Upload commit failed → ${ctx.wizard.state.repoName}`, { detail: err.message, isError: true });
      const errorHelpers = require('../lib/errorHelpers');
      const wasAuthError = await errorHelpers.replyGithubError(ctx, err, 'Upload failed');
      if (!wasAuthError) await ephemeral.sendEphemeral(ctx, '📍 Main Menu', bbtb.mainMenu);
    }
    });
    if (skipped) await ctx.reply('⏳ Already uploading — please wait a moment.');
    releasePendingFiles(ctx);
    return ctx.scene.leave();
}

/** Stores the scheduled_uploads row and confirms — called from both the
 * quick-pick and custom-time paths above, once a concrete scheduledFor
 * Date has been produced either way. */
async function finalizeUploadSchedule(ctx, scheduledFor, tz) {
  const changed = ctx.wizard.state.pendingFiles.filter((f) => f.status !== 'unchanged');
  const file = changed[0];
  const message = ctx.wizard.state.pendingCommitMessage;
  const repoName = ctx.wizard.state.repoName;

  const lowerName = file.filename.toLowerCase();
  const isArchive = lowerName.endsWith('.zip') || lowerName.endsWith('.tar') || lowerName.endsWith('.tar.gz') || lowerName.endsWith('.tgz');

  const scheduledUploads = require('../lib/scheduledUploads');
  await scheduledUploads.create(ctx.from.id, {
    repoName,
    targetPath: file.path,
    commitMessage: message,
    fileId: file.fileId,
    fileName: file.filename,
    isArchive,
    archiveAction: isArchive ? 'asis' : null,
    scheduledFor,
  });

  const timezone = require('../lib/timezone');
  const users = require('../lib/users');
  const user = await users.getUser(ctx.from.id);
  await ctx.reply(
    `📤 Scheduled: "${file.path}" will be uploaded to ${repoName} ${timezone.formatInZone(scheduledFor, tz, { hour12: user.time_format === '12h' })} (${tz}).\n\n` +
    `Manage it anytime in 🤖 Automation → 📤 Scheduled Uploads.`,
    bbtb.mainMenu
  );
  releasePendingFiles(ctx);
  return ctx.scene.leave();
}

function statusIcon(status) {
  return { new: '🆕', modified: '✏️', unchanged: '➖' }[status] || '•';
}

async function promptForFile(ctx) {
  const dirLabel = ctx.wizard.state.presetDir ? ` (into ${ctx.wizard.state.presetDir}/)` : '';
  await ctx.reply(
    `📤 Send a file to upload to ${ctx.wizard.state.repoName}${dirLabel}\n\n` +
    `📦 .zip, .tar, .tar.gz/.tgz — I\u2019ll ask whether to extract the contents (max ${format.formatBytes(config.MAX_ZIP_SIZE_BYTES)}) or upload the archive itself as one file (max ${format.formatBytes(config.MAX_SINGLE_FILE_BYTES)}).\n` +
    `📁 Anything else, including .rar/.7z — uploaded as-is (max ${format.formatBytes(config.MAX_SINGLE_FILE_BYTES)}); those two can\u2019t be extracted, only .zip/.tar formats can.\n\n` +
    `🔒 Password-protected zips are supported — I'll ask for the password if one's needed.\n\n` +
    `⚠️ Send it as a document/file attachment (📎 icon → File) — not via the photo/gallery picker, which compresses images and would alter the file's bytes.`,
    bbtb.cancelOnly
  );
  return ctx.wizard.selectStep(1);
}

function withPresetDir(ctx, path) {
  const dir = ctx.wizard.state.presetDir;
  return dir ? `${dir}/${path}` : path;
}

async function classifyFiles(ctx, fileRefs) {
  const token = await requireConnected(ctx);
  if (!token) return null;
  const user = await repoCache.getUser(ctx.from.id, token);

  let existingTree = [];
  try {
    existingTree = await github.getTree(token, user.login, ctx.wizard.state.repoName);
  } catch (_) {
    // empty/new repo — everything is new
  }
  const existingByPath = new Map(existingTree.map((e) => [e.path, e.sha]));

  const classified = await Promise.all(fileRefs.map(async (f) => {
    const content = fileBufferCache.get(f.contentRef);
    const existingSha = existingByPath.get(f.path);
    const localSha = gitBlobSha(content);
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
    return { ...f, status, oldSize, newSize: format.formatBytes(f.size) };
  }));

  if (ctx.wizard.state.mode === 'replaceFolder') {
    const targetDir = ctx.wizard.state.presetDir || '';
    const prefix = targetDir ? `${targetDir}/` : '';
    const uploadedPaths = new Set(fileRefs.map((f) => f.path));
    ctx.wizard.state.toDelete = existingTree
      .filter((e) => e.path.startsWith(prefix) && !uploadedPaths.has(e.path))
      .map((e) => e.path);
  }

  return classified;
}

async function processSingleFile(ctx, buffer, filename, fileId = null, isBackNav = false) {
  if (!isBackNav) {
    // Cache the raw Buffer, not a UTF-8-decoded string — decoding here and
    // re-encoding on commit is lossy for anything that isn't valid UTF-8
    // text (images, PDFs, and other binary files would come out corrupted).
    const contentRef = fileBufferCache.put(buffer);
    // fileId (the ORIGINAL Telegram file_id, not the buffer cache ref) is
    // kept alongside for 📅 Scheduled Uploads — the buffer cache has a
    // short TTL, so a schedule firing hours or days later needs to
    // re-download from Telegram directly rather than relying on this
    // session's cache still being warm.
    ctx.wizard.state.pendingFiles = [{ filename, contentRef, fileId, size: buffer.length, path: null }];
    delete ctx.wizard.state.pendingFiles[0].status;
  }

  if (ctx.wizard.state.lockedPath && !isBackNav) {
    ctx.wizard.state.pendingFiles[0].path = ctx.wizard.state.lockedPath;
    return showSummary(ctx);
  }

  if (ctx.wizard.state.presetDir && !isBackNav) {
    ctx.wizard.state.pendingFiles[0].path = withPresetDir(ctx, ctx.wizard.state.pendingFiles[0].filename);
    return showSummary(ctx);
  }

  const token = await requireConnected(ctx);
  if (!token) return ctx.scene.leave();

  let structureLine = '';
  try {
    const user = await repoCache.getUser(ctx.from.id, token);
    const tree = await github.getTree(token, user.login, ctx.wizard.state.repoName);
    const topLevel = listDirectory(tree, '');
    if (topLevel.length > 0) {
      const preview = topLevel.slice(0, 8).map((e) => (e.type === 'tree' ? `📁 ${e.name}/` : `📄 ${e.name}`)).join('\n');
      structureLine = `\n\n📂 Current top-level contents:\n${preview}${topLevel.length > 8 ? `\n… and ${topLevel.length - 8} more` : ''}`;
    } else {
      structureLine = '\n\n📂 This repo is currently empty.';
    }
  } catch (_) { /* best-effort */ }

  const f = ctx.wizard.state.pendingFiles[0];
  const defaultsLib = require('../lib/defaults');
  const d = await defaultsLib.getDefaults(ctx.from.id);
  const pathButtons = [
    [style.callback('📁 Browse Folders', 'upload:choose:browse')],
    [style.callback('📍 Root Directory', 'upload:choose:root')],
  ];
  if (d && d.default_upload_path) {
    pathButtons.push([style.callback(`⭐ Use Default (${d.default_upload_path}/)`, 'upload:choose:default')]);
  }
  if (ctx.wizard.state.suggestedDir && ctx.wizard.state.suggestedDir !== (d && d.default_upload_path)) {
    pathButtons.push([style.callback(`🕘 Last Used Here (${ctx.wizard.state.suggestedDir}/)`, 'upload:choose:suggested')]);
  }
  await ctx.reply(
    `📄 Received: ${f.filename} (${format.formatBytes(f.size)})\nWhere should this go?${structureLine}`,
    {
      ...Markup.inlineKeyboard(pathButtons),
      ...Markup.keyboard([['⌨️ Type Path Instead'], ['❌ Cancel']]).resize(),
    }
  );
  return ctx.wizard.selectStep(2);
}

async function processZip(ctx, buffer, password) {
  await ctx.reply(`📦 Zip received (${format.formatBytes(buffer.length)}) — extracting...`);

  // 🔒 Password-protected zip detection — reads the encryption bit directly
  // out of the zip's own headers (lib/zipCrypto.js) rather than guessing at
  // adm-zip's error text, so this part is reliable regardless of version.
  const { isZipEncrypted } = require('../lib/zipCrypto');
  let encrypted = false;
  try {
    encrypted = isZipEncrypted(buffer);
  } catch (_) { /* malformed header scan — AdmZip's own parsing below will surface the real error */ }

  if (encrypted && !password) {
    ctx.wizard.state.pendingZipRef = ctx.wizard.state.pendingZipRef || fileBufferCache.put(buffer);
    ctx.wizard.state.awaitingZipPassword = true;
    await ephemeral.sendEphemeral(ctx, '🔒 This zip is password-protected. Send the password as text, or ❌ Cancel.', bbtb.cancelOnly);
    return;
  }

  let zip;
  try {
    const AdmZip = require('adm-zip');
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

  // Verify the password actually decrypts before doing anything else with
  // it — a wrong password re-prompts instead of failing the whole upload.
  // (This is the one part of password support that couldn't be tested
  // directly in this environment — adm-zip isn't installed here, so its
  // getData(password) behavior is taken from its documented API rather
  // than a live run. If a correct password still gets rejected here,
  // that's the spot to check first.)
  if (encrypted) {
    try {
      entries[0].getData(password);
    } catch (err) {
      ctx.wizard.state.pendingZipRef = ctx.wizard.state.pendingZipRef || fileBufferCache.put(buffer);
      ctx.wizard.state.awaitingZipPassword = true;
      await ephemeral.sendEphemeral(ctx, '🔒 That password didn\u2019t work. Send the correct password as text, or ❌ Cancel.', bbtb.cancelOnly);
      return;
    }
  }

  if (ctx.wizard.state.pendingZipRef) {
    fileBufferCache.release(ctx.wizard.state.pendingZipRef);
    delete ctx.wizard.state.pendingZipRef;
  }

  // Zip bomb guard: check total UNCOMPRESSED size from the entries'
  // metadata (available without actually decompressing anything) before
  // extracting a single byte. A small compressed file can still expand to
  // an enormous amount in memory — this catches that before it happens,
  // not after.
  const totalUncompressed = entries.reduce((sum, e) => sum + (e.header ? e.header.size : 0), 0);
  if (totalUncompressed > config.MAX_ZIP_UNCOMPRESSED_BYTES) {
    await ctx.reply(format.errorMessage(
      'Upload failed',
      `this zip decompresses to ${format.formatBytes(totalUncompressed)}, which exceeds the ${format.formatBytes(config.MAX_ZIP_UNCOMPRESSED_BYTES)} limit`,
      'This is usually caused by a highly-compressed or corrupted archive — check the zip and try again.'
    ));
    return;
  }

  const topLevels = new Set(entries.map((e) => e.entryName.split('/')[0]));
  let stripPrefix = '';
  if (topLevels.size === 1) {
    const only = [...topLevels][0];
    if (entries.every((e) => e.entryName.startsWith(`${only}/`))) {
      stripPrefix = `${only}/`;
    }
  }

  const fileRefs = entries.map((e) => {
    const relativePath = stripPrefix ? e.entryName.slice(stripPrefix.length) : e.entryName;
    // Keep the raw Buffer from the zip entry — same reasoning as the
    // single-file path above; a UTF-8 round-trip here would corrupt any
    // binary file bundled in the zip (images, fonts, etc.).
    const content = encrypted ? e.getData(password) : e.getData();
    const contentRef = fileBufferCache.put(content);
    return {
      path: withPresetDir(ctx, relativePath),
      contentRef,
      size: content.length,
    };
  });

  const classified = await classifyFiles(ctx, fileRefs);
  if (!classified) return ctx.scene.leave();

  ctx.wizard.state.pendingFiles = classified;
  return showSummary(ctx);
}

/** .tar and .tar.gz/.tgz — gzip decoding uses Node's built-in zlib (no
 * dependency), archive parsing uses lib/tarReader.js (also no dependency,
 * see that file for why it's hand-rolled instead of a package). */
async function processTar(ctx, buffer, gzipped) {
  await ctx.reply(`📦 ${gzipped ? 'tar.gz' : 'tar'} received (${format.formatBytes(buffer.length)}) — extracting...`);

  let raw = buffer;
  if (gzipped) {
    try {
      const zlib = require('zlib');
      raw = zlib.gunzipSync(buffer);
    } catch (err) {
      await ctx.reply(format.errorMessage('Upload failed', 'the file isn\u2019t a valid gzip stream', 'Re-export the archive and try again.'));
      return;
    }
  }

  // Same zip-bomb-style guard as the zip path, applied to the decompressed size.
  if (raw.length > config.MAX_ZIP_UNCOMPRESSED_BYTES) {
    await ctx.reply(format.errorMessage(
      'Upload failed',
      `this archive decompresses to ${format.formatBytes(raw.length)}, which exceeds the ${format.formatBytes(config.MAX_ZIP_UNCOMPRESSED_BYTES)} limit`,
      'Check the archive and try again.'
    ));
    return;
  }

  const { extractTar } = require('../lib/tarReader');
  let entries, skippedCount;
  try {
    ({ entries, skippedCount } = extractTar(raw));
  } catch (err) {
    await ctx.reply(format.errorMessage('Upload failed', 'the tar file appears corrupted', 'Re-export the archive and try again.'));
    return;
  }

  if (entries.length === 0 && skippedCount === 0) {
    await ctx.reply(format.errorMessage('Upload failed', 'the archive contains no readable files', 'Check the archive and try again.'));
    return;
  }
  if (skippedCount > 0) {
    await ctx.reply(
      `⚠️ ${skippedCount} file${skippedCount === 1 ? '' : 's'} skipped — ${skippedCount === 1 ? 'it has' : 'they have'} a path too long for this reader to handle safely (GNU long-filename entries). Shorten the path(s) and re-archive if you need ${skippedCount === 1 ? 'it' : 'them'} included.`
    );
  }
  if (entries.length === 0) return; // everything was a long-name entry — nothing left to upload

  const topLevels = new Set(entries.map((e) => e.name.split('/')[0]));
  let stripPrefix = '';
  if (topLevels.size === 1) {
    const only = [...topLevels][0];
    if (entries.every((e) => e.name.startsWith(`${only}/`))) stripPrefix = `${only}/`;
  }

  const fileRefs = entries.map((e) => {
    const relativePath = stripPrefix ? e.name.slice(stripPrefix.length) : e.name;
    const contentRef = fileBufferCache.put(e.data);
    return { path: withPresetDir(ctx, relativePath), contentRef, size: e.data.length };
  });

  const classified = await classifyFiles(ctx, fileRefs);
  if (!classified) return ctx.scene.leave();

  ctx.wizard.state.pendingFiles = classified;
  return showSummary(ctx);
}

async function showSummary(ctx) {
  if (ctx.wizard.state.pendingFiles.length === 1 && !ctx.wizard.state.pendingFiles[0].status) {
    const classified = await classifyFiles(ctx, ctx.wizard.state.pendingFiles);
    if (!classified) return ctx.scene.leave();
    ctx.wizard.state.pendingFiles = classified;
  }

  const files = ctx.wizard.state.pendingFiles;
  const counts = { new: 0, modified: 0, unchanged: 0 };
  files.forEach((f) => counts[f.status]++);
  const toDelete = ctx.wizard.state.toDelete || [];

  await ephemeral.sendEphemeral(ctx, '📦 Upload Summary', bbtb.uploadSummary);

  if (counts.new === 0 && counts.modified === 0 && toDelete.length === 0) {
    const names = files.map((f) => f.path).join(', ');
    releasePendingFiles(ctx);
    await ctx.reply(
      `📦 Upload Summary → ${ctx.wizard.state.repoName}\n` +
      `➖ No changes detected — ${files.length === 1 ? `"${names}" matches` : `all ${files.length} files match`} what's already in the repo.\n\n` +
      `Nothing to upload.`,
      Markup.inlineKeyboard([[style.callback('📦 Open Repo', `repo:${ctx.wizard.state.repoName}`)]])
    );
    return ctx.scene.leave();
  }

  const changeDetail = files
    .filter((f) => f.status === 'modified')
    .slice(0, 3)
    .map((f) => `✏️ ${f.path}: ${f.oldSize || '?'} → ${f.newSize}`)
    .join('\n');

  let text =
    `📦 Upload Summary → ${ctx.wizard.state.repoName}\n` +
    `🆕 New: ${counts.new}   ✏️ Modified: ${counts.modified}   ➖ Unchanged: ${counts.unchanged} (skipped)`;
  if (toDelete.length > 0) text += `   🗑 To Delete: ${toDelete.length}`;
  if (changeDetail) text += `\n\n${changeDetail}`;
  if (toDelete.length > 0) {
    text += `\n\n🗑 Will be REMOVED:\n${toDelete.slice(0, 5).join('\n')}${toDelete.length > 5 ? `\n… and ${toDelete.length - 5} more` : ''}`;
  }

  await ctx.reply(text, {
    ...Markup.inlineKeyboard([
      [style.callback('📋 View File List', 'upload:summary:list')],
      [style.callback('✅ Commit Changes', 'upload:commit'), style.callback('❌ Cancel', 'upload:cancel')],
    ]),
  });
  return ctx.wizard.selectStep(3);
}

module.exports = scene;
module.exports.releaseOnExternalLeave = releaseOnExternalLeave;
