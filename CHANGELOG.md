# Changelog

All notable changes to GitroHub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
