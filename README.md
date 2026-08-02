<div align="center">

# 🐙 GitroHub

### Your complete GitHub workspace in Telegram

**Manage, automate, and enhance your GitHub workflow without leaving Telegram.**

![Node](https://img.shields.io/badge/Node.js-24%20LTS-3c873a?style=for-the-badge&logo=node.js&logoColor=white)
![grammY](https://img.shields.io/badge/grammY-1.44.0-6e5bff?style=for-the-badge)
![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.0.0-22d3ee?style=for-the-badge)

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&duration=2600&pause=900&color=6E5BFF&center=true&vCenter=true&width=560&lines=Repositories.+Branches.+Commits.+Pull+Requests.;Upload+a+ZIP+%E2%86%92+GitroHub+pushes+it+for+you.;AES-256-GCM+encrypted.+OAuth+only.+No+PATs.;Owner-only.+Private.+Yours." alt="Typing SVG" />

</div>

---

## 📖 Table of Contents

- [✨ Overview](#-overview)
- [🧩 Feature Pillars](#-feature-pillars)
- [🏗️ Architecture](#️-architecture)
- [⚡ Quick Start](#-quick-start)
- [🔐 Security Model](#-security-model)
- [⌨️ Commands](#️-commands)
- [📁 Project Structure](#-project-structure)
- [🛠️ Tech Stack](#️-tech-stack)
- [📜 Docs](#-docs)
- [🗺️ Roadmap](#️-roadmap)

---

## ✨ Overview

GitroHub turns Telegram into a full GitHub client — repository management,
Git workflows, file uploads with automatic diffing, pull requests, issues,
Actions, releases, and automation, all through inline-button menus that feel
native to chat.

This instance is **owner-only by design**: a single `BOT_OWNER_ID` gates
every incoming update. Anyone else who messages the bot is silently
ignored — no reply, no logging beyond a debug trace, zero backend cost.

> 🔒 **Private repository. Proprietary license.** See [`LICENSE.md`](./LICENSE.md).

---

## 🧩 Feature Pillars

<table>
<tr>
<td width="50%" valign="top">

### 📦 Repositories
- Create · Delete · Rename · Fork
- Star / Watch / Archive
- Visibility, topics, description, homepage
- Collaborators & permissions
- 🔑 Secrets & environment variables
- 📊 Insights (commits, contributors, traffic)

### 🌿 Git Operations
- Branches — create, delete, compare, rename
- Commits — history, diff, revert, cherry-pick
- Bulk-delete merged branches

</td>
<td width="50%" valign="top">

### 📁 File Management
- Browse, view, edit, delete, move
- **Smart upload** — single file or ZIP, with
  automatic diff detection (new/modified/unchanged)
- ZIP wrapper-folder auto-detection & stripping
- `.gitignore`-aware filtering
- Download any repo as a ZIP

### 🚀 Smart Deploy
- Send a ZIP → language auto-detected → repo
  created → `.gitignore` generated → pushed →
  link returned. Zero questions asked.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🔀 Collaboration
- Pull Requests — create, merge, review requests
- Issues — labels, milestones, assignees
- GitHub Actions — trigger, re-run, logs, artifacts
- Releases — auto-generated notes

</td>
<td width="50%" valign="top">

### 🔐 Security & Automation
- GitHub OAuth (never PATs) · AES-256-GCM at rest
- Optional PIN lock on destructive actions
- Scheduled tasks · Trigger rules · Auto-merge
- Bulk multi-repo actions

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────┐      webhook       ┌──────────────────┐
│   Telegram   │ ─────────────────▶ │   Express Server  │
└─────────────┘                     │  (webhook + OAuth  │
                                     │   callback page)   │
┌─────────────┐      OAuth          └─────────┬─────────┘
│   GitHub     │ ◀───────────────────────────┘
└─────────────┘                               │
                                     ┌─────────▼─────────┐
                                     │     grammY Bot      │
                                     │  (owner-gated core)  │
                                     └──┬───────────────┬──┘
                            ┌───────────▼───┐   ┌───────▼────────┐
                            │  PostgreSQL     │   │     Redis       │
                            │  (durable data) │   │ (sessions/cache) │
                            └─────────────────┘   └─────────────────┘
```

- **Webhook mode**, not polling — instant, zero wasted requests.
- **Redis-backed sessions** — navigation state, pending actions, upload flow state.
- **Postgres** — users, preferences, pins, activity log, automation rules.
- **Response caching + rate-limit tracking** on every GitHub API call.

---

## ⚡ Quick Start

```bash
git clone <your-private-repo-url> gitrohub
cd gitrohub
npm install
cp .env.example .env   # fill in every value — see docs/DEPLOYMENT.md
npm run migrate
npm start
```

For a full walkthrough (Telegram bot creation, GitHub OAuth App setup,
Railway deployment, secret generation), see **[`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md)**.

---

## 🔐 Security Model

| Layer | Approach |
|---|---|
| **Access control** | Single `BOT_OWNER_ID` — every other user is silently dropped before any DB/API call |
| **Token storage** | AES-256-GCM, per-user derived key via scrypt — never stored in plaintext |
| **Authentication** | GitHub OAuth (Authorization Code flow) — Personal Access Tokens are never requested or accepted |
| **CSRF protection** | Single-use, 5-minute-expiring OAuth `state` tokens |
| **Destructive actions** | Explicit confirm/cancel screens; optional 4-digit PIN lock layer |
| **Disconnect** | Deletes the local token **and** revokes it on GitHub's side — true revocation, not just local deletion |
| **Secrets in chat** | Any message containing a raw secret value is deleted immediately after being read |

See [`docs/legal/privacy.md`](./docs/legal/privacy.md) for the full data-handling policy.

---

## ⌨️ Commands

Primary commands are registered with Telegram automatically on deploy, so
they appear in the `/` autocomplete menu:

```
/start     /menu      /repo      /upload
/security  /settings  /status    /help
/cancel
```

Diagnostic/developer commands stay **intentionally hidden** from
autocomplete (they still work when typed manually) — this is a single-owner
private bot, so cluttering the suggestion list with debugging tools didn't
make sense:

```
/ping      /version   /uptime    /whoami
/health    /logs      /pr        /issues
/clone
```

Plus custom shortcuts configurable via **⚙️ Settings → ⌨️ Commands & Shortcuts**.

---

## 📁 Project Structure

```
gitrohub/
├── src/
│   ├── bot/
│   │   ├── bot.js              # Wires all middleware + menu handlers
│   │   ├── middleware/         # Owner gate, sessions, guards
│   │   ├── menus/              # Every screen: repos, upload, security, etc.
│   │   ├── handlers/           # Pending-action dispatcher, URL detection
│   │   ├── keyboards/          # Reusable nav/keyboard builders
│   │   └── commands/           # /ping, /health, /status, etc.
│   ├── github/                 # Octokit wrappers — repos, branches, files,
│   │                           # commits, PRs, issues, actions, releases,
│   │                           # ZIP pipeline (wrapper detection, diffing)
│   ├── security/                # AES-256-GCM encryption, OAuth, PIN lock
│   ├── db/
│   │   ├── postgres/            # Pool, schema.sql, migrations, queries
│   │   └── redis/                # Sessions, cache, rate-limit tracking
│   ├── automation/               # Cron-based scheduled tasks
│   ├── web/                      # Express server, OAuth callback page
│   ├── utils/                    # Logger, error formatting, formatting helpers
│   └── config/                    # Environment validation
├── docs/                          # DEPLOYMENT.md + legal documents
├── scripts/                       # Standalone healthcheck script
├── .env.example
├── railway.json
├── CHANGELOG.md
├── LICENSE.md
└── package.json
```

---

## 🛠️ Tech Stack

| Layer | Choice |
|---|---|
| Runtime | Node.js 24 LTS, plain JavaScript (no TypeScript, no build step) |
| Bot framework | [grammY](https://grammy.dev) v1.44.0, webhook mode |
| GitHub API | [Octokit.js](https://github.com/octokit/octokit.js) (REST + GraphQL) |
| Database | PostgreSQL (`pg`, hand-written queries) |
| Cache / Sessions | Redis (`ioredis`) |
| Logging | `pino`, structured JSON in production |
| Hosting | Railway (Node runtime + Postgres plugin + Redis plugin) |

---

## 📜 Docs

- 📘 [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) — full deployment walkthrough
- 📐 [`docs/VERSIONING.md`](./docs/VERSIONING.md) — how version bumps work (one command, always in sync)
- 📗 [`CHANGELOG.md`](./CHANGELOG.md) — release history ([Keep a Changelog](https://keepachangelog.com) format)
- 📕 [`LICENSE.md`](./LICENSE.md) — proprietary, all rights reserved
- 📙 [`docs/legal/`](./docs/legal/) — Terms of Service, Privacy Policy, Acceptable Use Policy

---

## 🗺️ Roadmap

See the `[Unreleased]` section of [`CHANGELOG.md`](./CHANGELOG.md) for what's
planned next: deploy key management, full backup/restore, repository
templates, draft PRs, and native secret-scanning alert surfacing.

---

<div align="center">

Built with 💜 for developers who live in chat.

**GitroHub v1.0.0**

</div>
