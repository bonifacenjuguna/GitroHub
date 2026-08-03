# Changelog

All notable changes to GitroHub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-08-02

### Fixed
- Trim upload progress messages to a bare hourglass emoji per preference (Telegram animates it natively); confirmed no latency regressions from the 1.2.0 upload rework

## [1.2.0] - 2026-08-02

### Fixed
- **Full rework of the ZIP upload pipeline** — reported symptom: after
  choosing "Strip wrapper", "Commit All" would hang with no response, and
  if it did eventually respond, every subsequent tap did nothing while
  duplicate "✅ Committed" messages piled up. Root causes, all in
  `src/github/zipPipeline.js`:
  - **Sequential diff checking:** every file in the ZIP was checked
    against the repo one at a time, in a `for` loop — a 30-file project
    meant 30 sequential network round-trips before the comparison screen
    could even appear. Now runs with capped concurrency (8 at a time via
    a small worker-pool helper), dramatically cutting wait time without
    hammering GitHub's API hard enough to trip secondary rate limits.
  - **Sequential per-file commits:** the actual commit step was creating
    one full GitHub commit per file, one at a time — not the single
    atomic commit originally designed for a ZIP push. Rewritten to use
    the Git Data API directly: create a blob per file (parallel, capped
    concurrency), build one tree from the branch's current tree plus all
    new/updated blobs, create one commit, move the branch ref. A 30-file
    project now produces exactly one commit instead of 30, and finishes
    in a fraction of the time.
  - **Duplicate/competing runs:** the tap-deduplication guard only held
    its lock for 2 seconds — far shorter than a real multi-file commit
    could take, especially under the old sequential approach. If Telegram
    redelivered the update mid-commit, a second identical commit run
    would fire concurrently, racing the first and producing the
    duplicate-message, "nothing happens now" behavior reported. Replaced
    with an explicit `committing` flag on the upload session that's held
    for the actual duration of the operation (not a fixed timer) and
    checked before starting — a genuinely duplicate tap now gets a clean
    "Already committing, please wait" instead of triggering a second run.
  - Added an immediate "⏳ Committing N files..." acknowledgment before
    the heavy work starts, so a large project doesn't look unresponsive
    while it's genuinely still working.
  - A failed commit now surfaces a proper formatted error (via the
    existing error-formatting standard) instead of silently vanishing
    after the progress message with nothing logged but a swallowed
    background error.

## [1.1.1] - 2026-08-02

### Fixed
- **Slow, delayed responses ("takes forever, then answers all at once"):**
  every GitHub API call anywhere in the bot was independently reconstructing
  the Octokit client from scratch — a fresh Postgres read plus a fresh
  scrypt-based AES-256-GCM decryption (scrypt is deliberately CPU-slow by
  design) *per call*. A single screen like Repo Detail fires 6+ GitHub
  calls concurrently via `Promise.all`, so that overhead was compounding
  every time. Fixed with a short-lived (5-minute) in-memory client cache
  in `src/github/client.js`, invalidated immediately on disconnect and
  reconnect so a revoked or replaced token can never be used past its
  validity window via a stale cached client.
- **Webhook timeout handling:** configured `webhookCallback`'s
  `timeoutMilliseconds`/`onTimeout` explicitly (`onTimeout: 'return'`) so
  a handler that runs long closes the HTTP response to Telegram cleanly
  instead of throwing. Update processing continues in the background via
  direct Bot API calls either way — this only affects how fast we
  acknowledge the webhook delivery itself. Previously, a slow handler
  caused Telegram to treat the delivery as failed and retry roughly every
  60 seconds, each retry hitting the same slow path and timing out again.
- **Noisy/unreadable error logs:** the `unhandledRejection` safety net
  added in 1.1.0 was logging the entire error object, which for GrammyError
  includes the full `ctx` (entire Telegram update, complete inline
  keyboard reply_markup, etc.) — producing walls of unreadable log noise
  for a single error. Now logs only `message`, `name`, and `description`.

## [1.1.0] - 2026-08-02

### Added
- Post-OAuth confirmation message now includes an inline "🐙 Go to Main
  Menu" button, so connecting GitHub no longer requires manually typing
  `/start` to reach the menu.
- Primary user-facing commands (`/start`, `/menu`, `/repo`, `/upload`,
  `/security`, `/settings`, `/status`, `/help`, `/cancel`) are now
  registered with Telegram automatically on every deploy via
  `setMyCommands`, so they appear in the `/` autocomplete menu. This is a
  deliberate reversal of the original v1.0.0 design, which intentionally
  left every command hidden from BotFather. Diagnostic/developer commands
  (`/ping`, `/health`, `/whoami`, `/version`, `/uptime`, `/logs`, `/pr`,
  `/issues`, `/clone`) remain unregistered on purpose — they still work
  when typed, they just don't clutter the suggestion list.

### Fixed
- **Critical crash fix:** expired/stale Telegram callback queries (tapping
  an inline button after ~30-60s, or double-tapping) were causing
  `ctx.answerCallbackQuery()` to reject with a 400 error that nothing was
  awaiting — an unhandled promise rejection, which Node terminates the
  entire process for by default. This was the actual root cause of the
  repeated Active → Crashed → redeploy cycling seen in production.
  Fixed by centrally wrapping `ctx.answerCallbackQuery()` in
  `contextExtensions.js` so every call site across the whole bot is
  protected automatically, plus a process-level `unhandledRejection`
  safety net in `index.js` as a second layer of protection against any
  future unforeseen rejection anywhere else in the codebase.

## [1.0.4] - 2026-08-02

### Fixed
- Clarify DOMAIN protocol error message to explain it breaks the Telegram webhook itself, not just OAuth

## [1.0.3] - 2026-08-02

### Fixed
- Fail fast at startup if DOMAIN is missing its https:// protocol, instead of silently building a malformed GitHub OAuth redirect_uri

## [1.0.2] - 2026-08-01

### Fixed
- Fix greedy regex in files.js causing file edit/download/delete callbacks to be misrouted to the generic file-view handler

## [1.0.1] - 2026-08-01

### Fixed
- Fix startup order causing false healthcheck failures and silent webhook non-registration; suppress harmless git stderr noise in /version

## [1.0.0] - 2026-07-31

### Added
- 🐙 **Repositories** — full lifecycle management: create, delete, rename, fork,
  archive, star/watch, visibility control, topics, description, homepage URL,
  collaborators, secrets & variables, insights/analytics.
- 🌿 **Branches** — create, delete, rename, compare, set default, bulk-delete
  merged branches.
- 📝 **Commits** — history browsing, diff viewing, revert, cherry-pick, search.
- 📁 **File Management** — browse, view, edit, delete, move, download ZIP,
  in-repo code search.
- 📤 **Upload/Deploy** — single-file and ZIP project upload with automatic
  diff detection (new / modified / unchanged), ZIP wrapper-folder detection
  and stripping, `.gitignore`-aware filtering, and a folder-scoped
  "Upload Here" shortcut.
- 🚀 **Smart Deploy** — one-tap ZIP-to-live-repo pipeline with automatic
  language/framework detection.
- 🔀 **Pull Requests** — create, merge (merge/squash/rebase), close,
  reviewer requests, diff viewing.
- 🐛 **Issues** — create, close/reopen, comment, labels, milestones.
- ⚙️ **GitHub Actions** — view runs, trigger workflows, re-run, cancel,
  view logs, download artifacts.
- 🚀 **Releases** — create with auto-generated notes, edit, delete.
- 🔐 **Security** — GitHub OAuth (Authorization Code flow), AES-256-GCM
  encrypted token storage, PIN lock for destructive actions, activity log,
  full account disconnect with server-side token revocation.
- ⚡ **Automation** — scheduled tasks (cron-based), trigger rules,
  auto-merge rules, bulk multi-repo actions.
- 📊 **Analytics** — commit activity, contributors, repository traffic.
- 🔍 **Global Search** — code, repositories, users, organizations across
  all accessible repos.
- 📋 **Gists** — create and browse code snippets.
- 🛠️ **Developer Tools** — raw API explorer, rate-limit monitor.
- ⚙️ **Settings** — account profile editing, display preferences, default
  repo behavior, custom command shortcuts, notification preferences.
- 🔒 **Owner-only access control** — every update is gated on a single
  Telegram user ID; all other users are silently ignored with zero
  backend cost.
- 🎨 **Animated OAuth callback page** with staged progress indicators.
- 📜 Hidden diagnostic commands: `/ping`, `/health`, `/status`, `/whoami`,
  `/version`, `/uptime`, `/cancel`, and more — not registered with
  BotFather, usable only by the owner.

### Security
- All GitHub tokens encrypted at rest with AES-256-GCM, unique
  per-account derived keys via scrypt.
- OAuth state tokens are single-use and expire after 5 minutes
  (CSRF protection).
- No Personal Access Tokens are ever requested or stored — OAuth only.
- Disconnecting revokes the token on GitHub's side, not just locally.

---

## [Unreleased]

Planned for future releases — not yet implemented:
- Deploy key management UI
- Full backup/restore system with scheduled snapshots
- Repository templates ("create from template")
- Draft PR toggle + `.github/PULL_REQUEST_TEMPLATE.md` auto-fill
- Secret scanning alert surfacing from GitHub's native detection
