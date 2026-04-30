<div align="center">

<img src="https://img.shields.io/badge/GitroHub-Bot-5865F2?style=for-the-badge&logo=telegram&logoColor=white" alt="GitroHub"/>

# 🤖 GitroHub

### Your GitHub, living inside Telegram.

Manage repos · Commit code · Upload files · Handle branches & PRs  
**— all without leaving Telegram.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PTB](https://img.shields.io/badge/python--telegram--bot-20.7-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://github.com/python-telegram-bot/python-telegram-bot)
[![PyGithub](https://img.shields.io/badge/PyGithub-2.1.1-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PyGithub/PyGithub)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app)
[![License](https://img.shields.io/badge/License-Private-red?style=flat-square)](.)
[![Version](https://img.shields.io/badge/Version-1.2.0-brightgreen?style=flat-square)](.)

</div>

---

## 📖 Table of Contents

- [✨ What is GitroHub?](#-what-is-gitrohub)
- [🎯 Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [📁 Project Structure](#-project-structure)
- [⚙️ Setup & Deployment](#️-setup--deployment)
  - [Prerequisites](#-prerequisites)
  - [Step 1 — Create Telegram Bot](#step-1--create-your-telegram-bot)
  - [Step 2 — GitHub OAuth App](#step-2--create-github-oauth-app)
  - [Step 3 — Generate Encryption Key](#step-3--generate-your-aes-256-encryption-key)
  - [Step 4 — Get Your Telegram ID](#step-4--get-your-telegram-user-id)
  - [Step 5 — Deploy on Railway](#step-5--deploy-on-railway)
  - [Step 6 — Configure BotFather](#step-6--configure-botfather)
- [🔑 Environment Variables](#-environment-variables)
- [📋 Commands Reference](#-commands-reference)
- [🔒 Security](#-security)
- [🛠️ Tech Stack](#️-tech-stack)
- [🚨 Troubleshooting](#-troubleshooting)
- [📜 Changelog](#-changelog)

---

## ✨ What is GitroHub?

**GitroHub** is a self-hosted, private Telegram bot that puts your entire GitHub workflow directly inside Telegram. No browser. No GitHub web UI. No context switching.

It connects to your GitHub account via **OAuth**, stores your session with **AES-256-GCM** encryption, and exposes a full interactive button-driven UI inside Telegram — from browsing your file tree, to committing code, to managing branches and pull requests.

> 🔐 **Private by design** — GitroHub is a single-owner bot. Only your Telegram user ID can interact with it. Everyone else sees a private access message.

---

## 🎯 Features

### 📦 Repository Management
- Browse all your GitHub repos with pagination, sorting (by date, stars, size, A–Z)
- Open, pin, and switch between repos instantly
- Create new repos with visibility, license, .gitignore and starter file options
- Toggle public ↔ private visibility
- Delete repos with 3-step confirmation safety flow
- Clone any public GitHub repo into your Projects

### 📂 File Operations
- **Interactive file browser** with breadcrumb navigation
- Read file contents directly in chat
- Edit files inline — send new content as a Telegram message
- Delete files (with confirmation)
- Move & rename files across paths
- Search inside the active repo by filename or content
- Copy raw file URL to clipboard

### ⬆️ Upload Modes
| Mode | What it does |
|------|-------------|
| `/upload <path>` | Upload a single file to a specific path |
| `/batch` | Upload multiple files, review changes before commit |
| `/mirror` | ZIP upload — full mirror, overwrites everything |
| `/update` | ZIP upload — add & modify only, skips deletions |

All upload modes show a **change preview** (new / modified / unchanged) before committing, with auto-generated or custom commit messages.

### 🌿 Branch Management
- List all branches with protection status
- Create new branches from any base
- Switch your active working branch
- Merge branches with conflict detection
- Compare branches with a diff view
- Delete merged branches safely

### 📜 Commit History
- View last 10 commits with SHA, message and timestamp
- **Undo last commit** (soft reset — keeps changes)
- **Rollback to any commit** (hard reset with confirmation)
- Reuse recent commit messages from a history picker

### 📊 Stats & Insights
- Repo stats: size, total commits, commit streak, stars, forks
- Language breakdown bar
- Top contributors with commit counts
- Traffic report: views & clones (last 14 days)
- GitHub profile summary: repos, stars, followers, top language

### 📝 Issues & Releases
- View, create and close GitHub Issues
- View releases with tags, dates and direct links
- Create and delete releases from Telegram

### ⬇️ Downloads
- Download any repo as a ZIP via direct link
- Download by GitHub URL without setting an active repo
- Download starred repos on the fly

### 👤 Multi-Account Support
- Connect and manage **multiple GitHub accounts**
- Switch between accounts with a single tap
- Each account gets its own encrypted session, active repo and branch memory
- Disconnect any account cleanly (GitHub data untouched)

### ⚙️ Personalization
- Custom private access message (shown to non-owners)
- Saved favourite paths (quick-jump shortcuts)
- Command aliases — define `/deploy` → `/upload src/deploy.sh`
- Commit message templates
- Bot settings panel

---

## 🏗️ Architecture

```
Telegram User
     │
     ▼
┌─────────────────────────────────────────┐
│             Telegram Bot API            │
│      (webhook / polling via PTB)        │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│               main.py                   │
│  • CommandHandler router                │
│  • CallbackQueryHandler router          │
│  • Text message state machine           │
└──┬──────────┬──────────┬────────────────┘
   │          │          │
   ▼          ▼          ▼
handlers/  handlers/  handlers/  ...
auth.py    repos.py   files.py
   │
   ▼
┌─────────────────────────────────────────┐
│            utils/github_helper.py       │
│  • PyGithub client per session          │
│  • Error messages, size/time formatters │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│              GitHub API v3              │
└─────────────────────────────────────────┘
              ▲
              │  (encrypted token lookup)
┌─────────────┴───────────────────────────┐
│           database/db.py                │
│  • PostgreSQL via psycopg2              │
│  • Sessions, state, recent repos,       │
│    pinned repos, settings, aliases      │
└─────────────┬───────────────────────────┘
              │
┌─────────────┴───────────────────────────┐
│          utils/encryption.py            │
│  • AES-256-GCM token encryption         │
│  • Key from AES_ENCRYPTION_KEY env var  │
└─────────────────────────────────────────┘
```

**OAuth Flow:**
```
User taps "Connect GitHub Account" (URL button)
        │
        ▼
GitHub authorization page
        │  (user approves)
        ▼
GET /auth/github/callback?code=...&state=...
        │
        ▼
Exchange code → access token → encrypt → store in DB
        │
        ▼
Bot sends "✅ Connected!" message to user
```

---

## 📁 Project Structure

```
gitrohub_v1.1/
│
├── 📄 main.py                  # Bot entry point + central callback router
├── 📄 requirements.txt         # All Python dependencies with pinned versions
├── 📄 Procfile                 # Railway process definition
├── 📄 railway.toml             # Railway deployment config
├── 📄 .env.example             # Environment variables template
│
├── 📂 database/
│   ├── __init__.py
│   └── db.py                   # PostgreSQL schema, session CRUD, state machine,
│                               # aliases, saved paths, commit history
│
├── 📂 handlers/
│   ├── __init__.py
│   ├── auth.py                 # /login /logout /accounts /whoami /switchaccount
│   │                           # OAuth URL generation, OAuth callback handler
│   ├── core.py                 # /start /help /ping /status /version /cancel
│   │                           # escape_md(), setup_commands(), send_private_message()
│   ├── repos.py                # /repos /projects /create /use /delete /rename /visibility
│   │                           # Repo dashboard, pagination, sorting, pinning
│   ├── files.py                # /browse /read /edit /delete /search /move
│   │                           # Interactive file tree with breadcrumbs
│   ├── upload.py               # /upload /batch /mirror /update
│   │                           # Single, batch, and ZIP upload with change preview
│   ├── branches.py             # /branch /switch /merge /diff
│   │                           # Branch list, creation, merge, comparison
│   ├── history.py              # /log /undo /rollback
│   │                           # Commit history, soft reset, hard rollback
│   ├── extras.py               # /stats /profile /traffic /contributors
│   │                           # /issues /releases /star /stars /clone /download
│   └── settings.py             # /settings /privatemsg /savedpaths /aliases /templates
│
└── 📂 utils/
    ├── __init__.py
    ├── encryption.py           # AES-256-GCM encrypt/decrypt for GitHub tokens
    └── github_helper.py        # get_github_client(), format helpers, error messages
```

---

## ⚙️ Setup & Deployment

### 📋 Prerequisites

Before you start, make sure you have:

- ✅ A **GitHub account**
- ✅ A **Telegram account**
- ✅ A [Railway.app](https://railway.app) account (free tier works)
- ✅ Python 3.11+ (only needed if running locally)

---

### Step 1 — Create Your Telegram Bot

1. Open Telegram and message **[@BotFather](https://t.me/BotFather)**
2. Send `/newbot`
3. Choose a name (e.g. `GitroHub`) and a username (e.g. `@MyGitroHubBot`)
4. Copy the **Bot Token** — looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

> ⚠️ Keep your bot token secret. It gives full control over your bot.

---

### Step 2 — Create GitHub OAuth App

1. Go to **GitHub → Settings → Developer settings → OAuth Apps**
2. Click **"New OAuth App"**
3. Fill in the form:

| Field | Value |
|-------|-------|
| Application name | `GitroHub` |
| Homepage URL | `https://your-app.railway.app` |
| Authorization callback URL | `https://your-app.railway.app/auth/github/callback` |

4. Click **Register application**
5. Copy your **Client ID**
6. Click **"Generate a new client secret"** and copy the **Client Secret**

> ⚠️ You can only see the client secret once — save it immediately.

---

### Step 3 — Generate Your AES-256 Encryption Key

This key encrypts your GitHub OAuth tokens in the database. Run once in any terminal:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Example output:
```
a3f8c2d1e4b5...64 hex characters...9f2e1a0b
```

Save this — it's your `AES_ENCRYPTION_KEY`.

> ⚠️ If you lose this key, all stored sessions become unreadable. Back it up securely.

---

### Step 4 — Get Your Telegram User ID

Message **[@userinfobot](https://t.me/userinfobot)** on Telegram.  
It replies instantly with your numeric user ID (e.g. `123456789`).

This ID goes into `TELEGRAM_ADMIN_ID` — only this ID can use your bot.

---

### Step 5 — Deploy on Railway

1. Push the project to a **private** GitHub repository
2. Go to **[railway.app](https://railway.app)** → **New Project** → **Deploy from GitHub repo**
3. Select your repo
4. Add a **PostgreSQL** database plugin:
   - Click **"+ New"** → **"Database"** → **"PostgreSQL"**
   - Railway auto-injects `DATABASE_URL` into your environment
5. Go to your service → **Variables** → add all environment variables:

```env
TELEGRAM_BOT_TOKEN      = your_bot_token_from_botfather
TELEGRAM_ADMIN_ID       = your_telegram_user_id_number
GITHUB_CLIENT_ID        = your_github_oauth_client_id
GITHUB_CLIENT_SECRET    = your_github_oauth_client_secret
WEBHOOK_URL             = https://your-app.railway.app
AES_ENCRYPTION_KEY      = your_generated_64_char_hex_key
PORT                    = 8080
```

> `GITHUB_REDIRECT_URI` is **auto-built** from `WEBHOOK_URL` — you don't need to set it separately unless you want to override it.

6. Railway will auto-detect `Procfile` and deploy — watch the logs for:
```
✅ Bot commands registered with Telegram
✅ Webhook set to https://your-app.railway.app/webhook
🚀 GitroHub Bot running on port 8080
```

7. Open Telegram → find your bot → send `/start` 🎉

---

### Step 6 — Configure BotFather

Set a description and about text for when users find your bot:

```
/setdescription → @YourBotUsername →
Manage your GitHub directly from Telegram.
Repos, commits, branches & more. 🚀
```

```
/setabouttext → @YourBotUsername →
Full GitHub management from Telegram.
Commit, push and control your workflow. ⚙️
```

Upload your GitroHub logo as the bot profile picture via `/setuserpic`.

> ✅ Do **not** set commands manually in BotFather — GitroHub registers all commands automatically every time the bot starts.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Your bot token from @BotFather |
| `TELEGRAM_ADMIN_ID` | ✅ | Your Telegram numeric user ID |
| `GITHUB_CLIENT_ID` | ✅ | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | ✅ | GitHub OAuth App client secret |
| `WEBHOOK_URL` | ✅ | Your Railway public URL (no trailing slash) |
| `AES_ENCRYPTION_KEY` | ✅ | 64-character hex key for token encryption |
| `DATABASE_URL` | ✅ | PostgreSQL connection string (Railway auto-fills) |
| `PORT` | ✅ | HTTP port for webhook server (default: `8080`) |
| `GITHUB_REDIRECT_URI` | ⬜ | Auto-built from `WEBHOOK_URL` — only override if needed |

---

## 📋 Commands Reference

### 🔐 Auth
| Command | Description |
|---------|-------------|
| `/start` | Welcome screen + connect GitHub button |
| `/login` | Connect a GitHub account via OAuth |
| `/logout` | Disconnect the active GitHub account |
| `/accounts` | Manage all connected GitHub accounts |
| `/switchaccount` | Switch between connected accounts |
| `/whoami` | Current account info, token status & API usage |

### 📦 Repos
| Command | Description |
|---------|-------------|
| `/repos` | All repos with pagination, sorting & quick actions |
| `/projects` | Active, pinned & recent repos dashboard |
| `/create` | Create a new repo (name, visibility, license, starter) |
| `/use <repo>` | Set a repo as your active working repo |
| `/clone <url>` | Add any public GitHub repo to your projects |
| `/visibility` | Toggle active repo public ↔ private |

### 📂 Files
| Command | Description |
|---------|-------------|
| `/browse` | Interactive file browser with folder navigation |
| `/read <path>` | Read file contents in chat |
| `/edit <path>` | Edit a file — send new content as a message |
| `/move <from> <to>` | Move file to a new path |
| `/search <query>` | Search files by name inside the active repo |
| `/delete <path>` | Delete a file (with confirmation) |

### ⬆️ Upload
| Command | Description |
|---------|-------------|
| `/upload <path>` | Upload a single file to a specific repo path |
| `/batch` | Upload multiple files, preview changes, then commit |
| `/mirror` | ZIP upload — full mirror (overwrites entire repo) |
| `/update` | ZIP upload — adds and modifies only (safe mode) |

### ⬇️ Download
| Command | Description |
|---------|-------------|
| `/download` | Download the active repo as a ZIP |

### 🌿 Branches
| Command | Description |
|---------|-------------|
| `/branch` | View all branches with protection status |
| `/branch <name>` | Create a new branch |
| `/switch <name>` | Switch your active working branch |
| `/merge <branch>` | Merge a branch into the active branch |
| `/diff <b1> <b2>` | Compare two branches |

### 📜 History
| Command | Description |
|---------|-------------|
| `/log` | View last 10 commits with SHA, message and time |
| `/undo` | Reverse the last commit (soft reset) |
| `/rollback` | Roll back to a specific commit SHA |

### 📊 Stats & More
| Command | Description |
|---------|-------------|
| `/stats` | Repo stats: commits, streak, stars, languages |
| `/traffic` | Repo views & clones over last 14 days |
| `/contributors` | List top contributors |
| `/profile` | Your GitHub profile summary |
| `/issues` | View, create and close GitHub Issues |
| `/releases` | View and manage repo releases |
| `/star <user/repo>` | Star any GitHub repo |
| `/stars` | View your starred repos |

### ⚙️ Settings
| Command | Description |
|---------|-------------|
| `/settings` | Bot personalization panel |
| `/privatemsg` | Customize the message shown to non-owners |
| `/savedpaths` | Manage favourite file paths |
| `/aliases` | Create command shortcuts |
| `/templates` | Manage commit message templates |

### 🛠️ Utility
| Command | Description |
|---------|-------------|
| `/status` | Full bot status: account, repo, branch, API health |
| `/ping` | Quick health check with response time |
| `/version` | Bot version and changelog |
| `/help` | Full interactive help menu by category |
| `/cancel` | Cancel any in-progress action immediately |

---

## 🔒 Security

GitroHub is built with security as a first principle, since it handles credentials that have write access to your GitHub account.

| 🛡️ Protection | Details |
|----------------|---------|
| **AES-256-GCM Encryption** | All GitHub OAuth tokens are encrypted at rest using AES-256-GCM before being written to the database. The encryption key never touches the database. |
| **Single-Owner Access** | Only the `TELEGRAM_ADMIN_ID` you set can use the bot. All other users see a private access message. |
| **Environment Secrets** | Zero secrets in code. All credentials are loaded from environment variables at runtime. |
| **HTTPS Only** | Railway enforces SSL on all public endpoints. The OAuth callback and webhook only accept HTTPS traffic. |
| **OAuth CSRF Protection** | Every OAuth flow generates a unique `state` token. The callback validates this token before exchanging the code — preventing CSRF attacks. |
| **ZIP Slip Protection** | All ZIP uploads sanitize file paths before writing, preventing path traversal attacks. |
| **Confirmation Flows** | All destructive actions (file delete, repo delete, logout) require explicit confirmation. Repo deletion uses a 3-step flow. |
| **Token Isolation** | Each GitHub account is stored as an isolated encrypted session. Switching accounts never leaks tokens between sessions. |

---

## 🛠️ Tech Stack

| Library | Version | Role |
|---------|---------|------|
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | 20.7 | Async Telegram Bot framework |
| [PyGithub](https://github.com/PyGithub/PyGithub) | 2.1.1 | GitHub REST API v3 client |
| [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) | 2.9.9 | PostgreSQL database driver |
| [cryptography](https://cryptography.io/) | 41.0.7 | AES-256-GCM token encryption |
| [aiohttp](https://docs.aiohttp.org/) | 3.9.1 | Async HTTP server (webhook + OAuth callback) |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | 1.0.0 | `.env` file loading for local dev |
| [humanize](https://python-humanize.readthedocs.io/) | 4.9.0 | Human-readable sizes and time formatting |
| [Pygments](https://pygments.org/) | 2.17.2 | Syntax highlighting for code previews |
| [Pillow](https://python-pillow.org/) | 10.2.0 | Image processing utilities |

**Infrastructure:**
- 🚂 [Railway](https://railway.app) — Hosting & PostgreSQL
- 🐙 [GitHub API v3](https://docs.github.com/en/rest) — All GitHub operations
- 📡 [Telegram Bot API](https://core.telegram.org/bots/api) — Messaging layer

---

## 🚨 Troubleshooting

**Bot doesn't respond to `/start`**
> Check Railway logs. Ensure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_ID` are set correctly. Your numeric user ID must exactly match `TELEGRAM_ADMIN_ID`.

**OAuth callback fails / "GitHub didn't return an access token"**
> Make sure `WEBHOOK_URL` is your exact Railway public URL with no trailing slash. The GitHub OAuth App callback URL must be `https://your-app.railway.app/auth/github/callback`.

**"❌ Not logged in" after connecting**
> This can mean the `AES_ENCRYPTION_KEY` changed after sessions were stored. Re-generate a key, update the Railway variable, and re-login.

**Database errors on startup**
> Ensure the PostgreSQL plugin is added to your Railway project. The bot runs `init_db()` on startup and creates all tables automatically.

**Webhook not receiving updates**
> Railway assigns a new URL on re-deploy if you haven't set a custom domain. Update `WEBHOOK_URL` and the GitHub OAuth callback URL whenever your Railway URL changes.

**ZIP upload skips files**
> In `/mirror` mode, all files are replaced. In `/update` mode, only new and modified files are committed — unchanged files are skipped by design.

---

## 📜 Changelog

### v1.2.0 — Bug-Fix & Polish *(Apr 2026)*
- 🔗 "Connect GitHub Account" on `/start` is now a proper URL link button (shows the ↗ arrow)
- 🏠 Home button now renders the full dashboard — not just a plain text message
- ✅ All inline buttons now respond: Stats, Log, Branches, Issues, Releases, Help, Download
- 📋 All help category sections fully wired (Download, Issues, Releases, Stats)
- ⬇️ Download by URL flow fully implemented
- 🔄 Batch commit confirm flow fixed end-to-end
- 🔍 Repo search now works from inline button
- ⚙️ Repo Settings panel added
- 🐛 `do_batch_commit` and `do_zip_commit` implemented (were called but undefined)
- 🐛 `login_start` callback import error fixed

### v1.1.0 — Multi-Account Support
- 👤 Multiple GitHub accounts per bot instance
- 🔄 One-tap account switching
- 🗑️ Clean account removal flow

### v1.0.0 — Initial Release
- Full GitHub management via Telegram
- AES-256-GCM encrypted sessions
- ZIP mirror & update upload modes
- Interactive file browser with breadcrumbs
- Commit history, undo, and rollback
- Branch management & merging
- Releases, gists, stars, and profile
- Stats, traffic & contributor views
- Personalization settings & aliases

---

<div align="center">

Made with ❤️ — **GitroHub** · [@GitroHubBot](https://t.me/GitroHubBot)

*Secure · Fast · Always in sync with GitHub*

</div>
