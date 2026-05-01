<div align="center">

<img src="https://img.shields.io/badge/GitroHub-Telegram%20GitHub%20Bot-5865F2?style=for-the-badge&logo=telegram&logoColor=white" alt="GitroHub Banner"/>

<br/>
<br/>

# 🤖 GitroHub — Telegram GitHub Manager Bot

### Control GitHub from Telegram. No browser. No context switching. Just chat.

Create repos · Commit code · Upload files · Manage branches  
**All from inside Telegram — Secure, Fast, Always in sync.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PTB](https://img.shields.io/badge/python--telegram--bot-20.7-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://github.com/python-telegram-bot/python-telegram-bot)
[![PyGithub](https://img.shields.io/badge/PyGithub-2.1.1-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PyGithub/PyGithub)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app)
[![AES-256](https://img.shields.io/badge/Security-AES--256--GCM-critical?style=flat-square&logo=letsencrypt&logoColor=white)](#-security)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat-square)](#-license)
[![README](https://img.shields.io/badge/README-v1.1-brightgreen?style=flat-square)](#-changelog)
[![Bot](https://img.shields.io/badge/Telegram-@GitroHubBot-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://t.me/GitroHubBot)

</div>

---

## 📖 Table of Contents

<details open>
<summary>Click to expand / collapse</summary>

- [🖼️ Screenshots](#️-screenshots)
- [✨ What is GitroHub?](#-what-is-gitrohub)
- [⚡ Why GitroHub?](#-why-gitrohub)
- [🎯 Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [📁 Project Structure](#-project-structure)
- [🗄️ Database Schema](#️-database-schema)
- [⚙️ Setup & Deployment](#️-setup--deployment)
  - [Prerequisites](#-prerequisites)
  - [Step 1 — Create Telegram Bot](#step-1--create-your-telegram-bot)
  - [Step 2 — GitHub OAuth App](#step-2--create-github-oauth-app)
  - [Step 3 — Generate Encryption Key](#step-3--generate-your-aes-256-encryption-key)
  - [Step 4 — Get Your Telegram ID](#step-4--get-your-telegram-user-id)
  - [Step 5 — Deploy on Railway](#step-5--deploy-on-railway)
  - [Step 6 — Configure BotFather](#step-6--configure-botfather)
- [💻 Local Development](#-local-development)
- [🔑 Environment Variables](#-environment-variables)
- [📋 Commands Reference](#-commands-reference)
- [🔒 Security](#-security)
- [🛠️ Tech Stack](#️-tech-stack)
- [⚠️ Known Limitations](#️-known-limitations)
- [🗺️ Roadmap](#️-roadmap)
- [🚨 Troubleshooting](#-troubleshooting)
- [❓ FAQ](#-faq)
- [📜 Changelog](#-changelog)
- [🙏 Acknowledgements](#-acknowledgements)
- [⚖️ License](#️-license)

</details>

---

## 🖼️ Screenshots

<div align="center">

<table>
  <tr>
    <td align="center"><b>🤖 Bot Profile</b></td>
    <td align="center"><b>🏠 Dashboard</b></td>
  </tr>
  <tr>
    <td><img src="screenshots/profile.jpg" width="300" alt="GitroHub Bot Profile"/></td>
    <td><img src="screenshots/dashboard.jpg" width="300" alt="GitroHub Dashboard"/></td>
  </tr>
  <tr>
    <td align="center">Clean bot profile with logo &amp; bio</td>
    <td align="center">Full dashboard after <code>/start</code> — active repo, branch &amp; all actions</td>
  </tr>
</table>

</div>

> 💡 **Tip:** After `/start`, your active repo and branch appear instantly. Tap any button to act on them — no typing needed.

---

## ✨ What is GitroHub?

**GitroHub** is a self-hosted, single-owner Telegram bot that brings your entire GitHub workflow into Telegram. It eliminates the need to switch between apps by letting you create repositories, commit code, delete files, browse your file tree, manage branches, view stats, and automate development workflows — entirely from a Telegram chat.

It connects to your GitHub account via **OAuth 2.0**, encrypts your token with **AES-256-GCM**, and presents a full button-driven interactive UI — no commands to memorize, just tap.

> [!NOTE]
> GitroHub is a **private bot** — only the Telegram user ID you configure as `TELEGRAM_ADMIN_ID` can use it. It is designed to be your personal GitHub remote control, not a public service.

---

## ⚡ Why GitroHub?

<div align="center">

| Feature | GitroHub | GitHub Web | GitHub Mobile App |
|---------|:--------:|:----------:|:-----------------:|
| Works inside Telegram | ✅ | ❌ | ❌ |
| Full repo management | ✅ | ✅ | ⚠️ Limited |
| Commit & push files | ✅ | ✅ | ⚠️ Limited |
| ZIP upload (mirror / update) | ✅ | ❌ | ❌ |
| Batch file commits with preview | ✅ | ❌ | ❌ |
| Interactive file browser | ✅ | ✅ | ⚠️ |
| Multi-account switching | ✅ | ❌ | ❌ |
| AES-256-GCM token encryption | ✅ | N/A | N/A |
| Works on any device with Telegram | ✅ | ❌ | ❌ |
| No extra app to install | ✅ | ❌ | ❌ |
| Commit message templates | ✅ | ❌ | ❌ |
| Command aliases / shortcuts | ✅ | ❌ | ❌ |

</div>

**Key wins:**
- ⏱️ **Saves time** — no context switching between apps
- 📱 **Mobile-first** — full GitHub power from a phone keyboard
- 🔁 **Automation-ready** — batch uploads, mirror deploys, commit templates
- 🧠 **Stateful** — remembers your active repo, branch, and recent paths
- 🔐 **Yours alone** — self-hosted, zero third-party data exposure

---

## 🎯 Features

<details open>
<summary><b>📦 Repository Management</b></summary>

- Browse all your GitHub repos with pagination and sorting (by date, stars, size, A–Z)
- Pin and quick-switch between frequently used repos
- Create new repos with name, visibility, license, `.gitignore` template and starter file
- Toggle public ↔ private visibility in one tap
- Delete repos with a 3-step confirmation safety flow
- Clone any public GitHub repo into your Projects
- Repo dashboard showing stars, forks, size, language, and last push time

</details>

<details>
<summary><b>📂 File Operations</b></summary>

- **Interactive file browser** with folder navigation and breadcrumb trail
- Read file contents rendered in chat with syntax highlighting
- Edit files inline — send the new content as a Telegram message, commit instantly
- Delete files with a confirmation prompt
- Move & rename files across any path
- Search inside the active repo by filename or content string
- Copy raw GitHub file URL to share or use in CI

</details>

<details>
<summary><b>⬆️ Upload Modes</b></summary>

| Mode | Command | What it does |
|------|---------|-------------|
| Single file | `/upload <path>` | Upload one file to a specific repo path |
| Batch | `/batch` | Upload multiple files, preview full diff, then commit |
| Full mirror | `/mirror` | ZIP upload — overwrites entire repo to match ZIP contents |
| Safe update | `/update` | ZIP upload — adds and modifies only, never deletes existing files |

All modes show a **change preview** (🟢 new / 🟡 modified / ⚪ unchanged) before committing. Commit messages can be auto-generated or written manually.

</details>

<details>
<summary><b>🌿 Branch Management</b></summary>

- List all branches with protection status and default branch indicator
- Create new branches from any base ref
- Switch active working branch with one tap
- Merge branches with automatic conflict detection
- Side-by-side branch diff view
- Safely delete merged branches (protected branches are blocked)

</details>

<details>
<summary><b>📜 Commit History & Rollback</b></summary>

- View last 10 commits with SHA, author, message, and timestamp
- **Undo last commit** — soft reset, keeps working changes staged
- **Rollback to any commit** — hard reset with double-confirmation
- Pick and reuse recent commit messages from a history picker
- Commit message templates for repetitive or structured workflows

</details>

<details>
<summary><b>📊 Stats & Insights</b></summary>

- Repo stats: total commits, commit streak, stars, forks, watchers, open issues
- Language breakdown bar
- Top contributors ranked by commit count
- Traffic report: views, unique visitors, and clones over last 14 days
- GitHub profile summary: public repos, stars received, followers, top language, account age

</details>

<details>
<summary><b>📝 Issues & Releases</b></summary>

- View open issues with labels, assignees, and timestamps
- Create new issues with title and body directly from Telegram
- Close issues by number
- View releases with version tags, dates, and changelogs
- Create new releases with tag name, title, and description
- Delete releases with confirmation

</details>

<details>
<summary><b>⬇️ Downloads</b></summary>

- Download active repo as a ZIP — returns a direct GitHub link
- Download any repo by GitHub URL (no active repo needed)
- Download any of your starred repos on the fly
- Branch-aware — always downloads your active branch

</details>

<details>
<summary><b>👤 Multi-Account Support</b></summary>

- Connect and manage **multiple GitHub accounts** in one bot instance
- One-tap switching between accounts
- Each account has its own encrypted session, active repo, and branch memory
- Disconnect any account cleanly — no GitHub data is modified
- `/whoami` shows token status, API rate limit remaining, and account details

</details>

<details>
<summary><b>⚙️ Personalization & Automation</b></summary>

- Custom "private access" message shown to any non-owner who messages the bot
- Saved favourite paths — jump to common file locations instantly
- Command aliases — map `/deploy` → `/upload dist/app.js main`
- Commit message templates — fill-in-the-blank for CI, hotfixes, releases
- Bot settings panel with all preferences in one place

</details>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Telegram User                     │
└─────────────────────┬───────────────────────────────┘
                      │  Messages / Inline button taps
                      ▼
┌─────────────────────────────────────────────────────┐
│               Telegram Bot API                      │
│         (HTTPS webhook on Railway)                  │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                   main.py                           │
│  ┌─────────────────────────────────────────────┐   │
│  │  CommandHandler router  (/start, /repos …)  │   │
│  │  CallbackQueryHandler   (button taps)       │   │
│  │  MessageHandler         (text state machine)│   │
│  └──────┬──────────┬──────────┬───────────────┘   │
└─────────┼──────────┼──────────┼────────────────────┘
          │          │          │
          ▼          ▼          ▼
    handlers/   handlers/  handlers/  handlers/ ...
    auth.py     repos.py   files.py   upload.py
                                          │
                                          ▼
                          ┌───────────────────────────┐
                          │    utils/github_helper.py │
                          │  • PyGithub client factory│
                          │  • Rate limit handling    │
                          │  • Size & time formatters │
                          └──────────────┬────────────┘
                                         │
                                         ▼
                          ┌───────────────────────────┐
                          │       GitHub API v3        │
                          │  api.github.com/repos/... │
                          └───────────────────────────┘
                                         ▲
                                  (token lookup)
                          ┌───────────────────────────┐
                          │      database/db.py        │
                          │  • PostgreSQL / psycopg2  │
                          │  • Sessions, state,       │
                          │    repos, aliases,        │
                          │    settings, paths        │
                          └──────────────┬────────────┘
                                         │
                          ┌──────────────┴────────────┐
                          │   utils/encryption.py     │
                          │  • AES-256-GCM encrypt    │
                          │  • Decrypt on token read  │
                          └───────────────────────────┘
```

**OAuth Flow:**
```
User taps "🔗 Connect GitHub Account" (URL link button ↗)
        │
        ▼
github.com/login/oauth/authorize?client_id=...&state=<csrf_token>
        │  User clicks "Authorize GitroHub"
        ▼
GET https://your-app.railway.app/auth/github/callback
    ?code=<auth_code>&state=<csrf_token>
        │
        ├─ Validate state token  (CSRF protection)
        ├─ Exchange code ──────► GitHub access token
        ├─ Encrypt token ──────► AES-256-GCM ciphertext
        ├─ Store ciphertext ───► PostgreSQL
        │
        ▼
Bot sends ✅ "Connected as @username!" to Telegram user
```

---

## 📁 Project Structure

```
gitrohub_v1.1/
│
├── 📄 main.py                  # Entry point: webhook server + central callback router
├── 📄 requirements.txt         # Pinned Python dependencies
├── 📄 Procfile                 # Railway process: web: python main.py
├── 📄 railway.toml             # Railway build & deploy configuration
├── 📄 .env.example             # Environment variable template
├── 📄 README.md                # This file
│
├── 📂 database/
│   ├── __init__.py
│   └── db.py                   # init_db(), sessions CRUD, state machine,
│                               # recent repos, pinned repos, aliases,
│                               # saved paths, commit templates, settings
│
├── 📂 handlers/
│   ├── __init__.py
│   ├── auth.py                 # /login /logout /accounts /whoami /switchaccount
│   │                           # OAuth URL generation, callback processing
│   ├── core.py                 # /start /help /ping /status /version /cancel
│   │                           # escape_md(), setup_commands(), BOT_VERSION
│   ├── repos.py                # /repos /projects /create /use /delete /rename
│   │                           # Repo dashboard, pagination, sort, pin, visibility
│   ├── files.py                # /browse /read /edit /delete /search /move
│   │                           # Interactive breadcrumb file tree
│   ├── upload.py               # /upload /batch /mirror /update
│   │                           # Change preview, commit message flow
│   ├── branches.py             # /branch /switch /merge /diff
│   │                           # Branch list, create, merge, compare
│   ├── history.py              # /log /undo /rollback
│   │                           # Commit history, soft reset, hard rollback
│   ├── extras.py               # /stats /profile /traffic /contributors
│   │                           # /issues /releases /star /stars /clone /download
│   └── settings.py             # /settings /privatemsg /savedpaths /aliases /templates
│
└── 📂 utils/
    ├── __init__.py
    ├── encryption.py           # AES-256-GCM encrypt() / decrypt() for GitHub tokens
    └── github_helper.py        # get_github_client(), formatters, error mapping
```

---

## 🗄️ Database Schema

GitroHub uses **PostgreSQL** with the following tables, all auto-created by `init_db()` on startup:

<details>
<summary><b>Click to view full schema</b></summary>

```sql
-- GitHub sessions — one row per connected account per user
CREATE TABLE sessions (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    github_username TEXT NOT NULL,
    access_token    TEXT NOT NULL,          -- AES-256-GCM encrypted ciphertext
    active_repo     TEXT,                   -- e.g. "bonifacenjuguna/GitroHub"
    active_branch   TEXT DEFAULT 'main',
    is_active       BOOLEAN DEFAULT TRUE,   -- currently selected account
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Conversation state machine — tracks what the bot is waiting for from the user
CREATE TABLE user_states (
    telegram_id     BIGINT PRIMARY KEY,
    state           TEXT,                   -- e.g. "awaiting_commit_message"
    state_data      JSONB DEFAULT '{}',     -- arbitrary context payload (files, paths, etc.)
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Pinned & recently accessed repos
CREATE TABLE user_repos (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    repo_full_name  TEXT NOT NULL,          -- e.g. "user/repo"
    is_pinned       BOOLEAN DEFAULT FALSE,
    last_used_at    TIMESTAMP DEFAULT NOW()
);

-- Custom command aliases
CREATE TABLE aliases (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    alias           TEXT NOT NULL,          -- e.g. "deploy"
    target          TEXT NOT NULL,          -- e.g. "/upload dist/app.js main"
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Saved file path shortcuts
CREATE TABLE saved_paths (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    label           TEXT NOT NULL,          -- e.g. "config"
    path            TEXT NOT NULL,          -- e.g. "src/config/settings.py"
    repo            TEXT NOT NULL
);

-- Commit message templates
CREATE TABLE commit_templates (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    label           TEXT NOT NULL,          -- e.g. "hotfix"
    template        TEXT NOT NULL           -- e.g. "fix: {description}"
);

-- Per-user bot settings
CREATE TABLE user_settings (
    telegram_id     BIGINT PRIMARY KEY,
    private_message TEXT DEFAULT 'This bot is private.',
    auto_commit_msg BOOLEAN DEFAULT TRUE,   -- auto-generate commit messages
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

</details>

---

## ⚙️ Setup & Deployment

### 📋 Prerequisites

| Requirement | Notes |
|-------------|-------|
| GitHub account | Free or paid |
| Telegram account | Any |
| [Railway.app](https://railway.app) account | Free tier works |
| Python 3.11+ | Only needed for local development |

---

### Step 1 — Create Your Telegram Bot

1. Open Telegram → message **[@BotFather](https://t.me/BotFather)**
2. Send `/newbot`
3. Choose a **name** (e.g. `GitroHub`) and a **username** (e.g. `@MyGitroHubBot`)
4. Copy the **Bot Token** — it looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

> [!WARNING]
> Keep your bot token secret. It gives full control over the bot. Never commit it to any repository.

---

### Step 2 — Create GitHub OAuth App

1. Go to **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
2. Fill in:

| Field | Value |
|-------|-------|
| Application name | `GitroHub` |
| Homepage URL | `https://your-app.railway.app` |
| Authorization callback URL | `https://your-app.railway.app/auth/github/callback` |

3. Click **Register application**
4. Copy the **Client ID**
5. Click **Generate a new client secret** → copy the **Client Secret**

> [!WARNING]
> The client secret is shown only once. Copy it before leaving the page.

---

### Step 3 — Generate Your AES-256 Encryption Key

Run this once in any terminal:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Example output:
```
a3f8c2d1e4b59f2e1a0b7d3c6e8f4a2b1c9d0e7f6a5b4c3d2e1f0a9b8c7d6e5
```

This 64-character hex string is your `AES_ENCRYPTION_KEY`.

> [!IMPORTANT]
> Back this key up securely. If you lose it or change it, all stored sessions become unreadable and all accounts must re-authenticate.

---

### Step 4 — Get Your Telegram User ID

Message **[@userinfobot](https://t.me/userinfobot)** on Telegram.  
It replies instantly with your numeric user ID, e.g. `123456789`.

This number goes into `TELEGRAM_ADMIN_ID`. Only this ID can use your bot.

---

### Step 5 — Deploy on Railway

1. Push the project to a **private** GitHub repository
2. Go to **[railway.app](https://railway.app)** → **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Add a **PostgreSQL** database:
   - Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
   - Railway auto-injects `DATABASE_URL` into your service environment
5. In your service → **Variables**, add:

```env
TELEGRAM_BOT_TOKEN      = your_bot_token
TELEGRAM_ADMIN_ID       = your_numeric_telegram_id
GITHUB_CLIENT_ID        = your_github_oauth_client_id
GITHUB_CLIENT_SECRET    = your_github_oauth_client_secret
WEBHOOK_URL             = https://your-app.railway.app
AES_ENCRYPTION_KEY      = your_64_char_hex_key
PORT                    = 8080
```

6. Railway auto-detects `Procfile` and deploys. Watch the logs for:

```
✅ Bot commands registered with Telegram
✅ Webhook set → https://your-app.railway.app/webhook
🚀 GitroHub v1.2.0 running on port 8080
```

7. Open Telegram → find your bot → send `/start` 🎉

---

### Step 6 — Configure BotFather

Send these to **[@BotFather](https://t.me/BotFather)**:

**Description** (`/setdescription`):
```
🚀 Manage GitHub directly from Telegram.
Create repositories, commit code, delete files, and automate
development workflows — all without leaving chat.
```

**About text** (`/setabouttext`):
```
Manage GitHub from Telegram 🚀
Commit, push and control your workflow ⚙️
@GitroHub
```

Upload your GitroHub logo via `/setuserpic`.

> [!TIP]
> Do **not** set commands manually in BotFather. GitroHub calls `setup_commands()` on every startup and registers all commands automatically.

---

## 💻 Local Development

Running GitroHub locally uses **polling** instead of a webhook — no public URL required for updates.

**1. Clone and install:**

```bash
git clone https://github.com/your-username/gitrohub.git
cd gitrohub
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Create your `.env`:**

```bash
cp .env.example .env
# Open .env and fill in all values
```

**3. Set up a local PostgreSQL database:**

```bash
# macOS (Homebrew)
brew install postgresql && brew services start postgresql
createdb gitrohub

# Ubuntu / Debian
sudo apt install postgresql
sudo -u postgres createdb gitrohub
```

Set `DATABASE_URL=postgresql://localhost/gitrohub` in your `.env`.

**4. Run in polling mode:**

```bash
# Leave WEBHOOK_URL empty to trigger polling mode automatically
WEBHOOK_URL="" python3 main.py
```

> [!NOTE]
> In polling mode, Telegram updates work without a public URL. However, the **GitHub OAuth callback** still needs to be reachable. Use [ngrok](https://ngrok.com) (`ngrok http 8080`) and temporarily set its URL as `WEBHOOK_URL` and in your GitHub OAuth App settings when logging in.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `TELEGRAM_ADMIN_ID` | ✅ | Your Telegram numeric user ID |
| `GITHUB_CLIENT_ID` | ✅ | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | ✅ | GitHub OAuth App client secret |
| `WEBHOOK_URL` | ✅ | Your Railway public URL (no trailing slash) |
| `AES_ENCRYPTION_KEY` | ✅ | 64-char hex key for AES-256-GCM encryption |
| `DATABASE_URL` | ✅ | PostgreSQL connection string (Railway auto-fills) |
| `PORT` | ✅ | HTTP port for the webhook server (default: `8080`) |
| `GITHUB_REDIRECT_URI` | ⬜ | Auto-built from `WEBHOOK_URL` — override only if needed |

---

## 📋 Commands Reference

<details open>
<summary><b>🔐 Auth & Accounts</b></summary>

| Command | Description |
|---------|-------------|
| `/start` | Welcome screen with connect button, or full dashboard if logged in |
| `/login` | Connect a GitHub account via OAuth |
| `/logout` | Disconnect the active GitHub account |
| `/accounts` | Manage all connected GitHub accounts |
| `/switchaccount` | Switch between connected accounts |
| `/whoami` | Current account info, token status & API rate limit remaining |

</details>

<details>
<summary><b>📦 Repos</b></summary>

| Command | Description |
|---------|-------------|
| `/repos` | All repos with pagination, sorting & quick actions |
| `/projects` | Active, pinned & recently used repos dashboard |
| `/create` | Create a new repo (name, visibility, license, starter file) |
| `/use <repo>` | Set a repo as your active working repo |
| `/clone <url>` | Add any public GitHub repo to your Projects |
| `/visibility` | Toggle active repo public ↔ private |

</details>

<details>
<summary><b>📂 Files</b></summary>

| Command | Description |
|---------|-------------|
| `/browse` | Interactive file browser with breadcrumb navigation |
| `/read <path>` | Read a file's contents in chat |
| `/edit <path>` | Edit a file — send new content as a message |
| `/move <from> <to>` | Move or rename a file |
| `/search <query>` | Search files by name inside the active repo |
| `/delete <path>` | Delete a file (with confirmation) |

</details>

<details>
<summary><b>⬆️ Upload</b></summary>

| Command | Description |
|---------|-------------|
| `/upload <path>` | Upload a single file to a specific repo path |
| `/batch` | Upload multiple files, preview all changes, then commit |
| `/mirror` | ZIP upload — full mirror, overwrites entire repo |
| `/update` | ZIP upload — add & modify only, never deletes |

</details>

<details>
<summary><b>⬇️ Download</b></summary>

| Command | Description |
|---------|-------------|
| `/download` | Download the active repo branch as a ZIP |

</details>

<details>
<summary><b>🌿 Branches</b></summary>

| Command | Description |
|---------|-------------|
| `/branch` | View all branches with protection status |
| `/branch <name>` | Create a new branch from the active base |
| `/switch <name>` | Switch your active working branch |
| `/merge <branch>` | Merge a branch into the active branch |
| `/diff <b1> <b2>` | Compare two branches |

</details>

<details>
<summary><b>📜 History</b></summary>

| Command | Description |
|---------|-------------|
| `/log` | View last 10 commits with SHA, message and timestamp |
| `/undo` | Reverse the last commit (soft reset, keeps changes) |
| `/rollback` | Roll back to a specific commit SHA (hard reset) |

</details>

<details>
<summary><b>📊 Stats, Issues & Releases</b></summary>

| Command | Description |
|---------|-------------|
| `/stats` | Repo stats: commits, streak, stars, languages |
| `/traffic` | Traffic: views & clones over last 14 days |
| `/contributors` | Top contributors ranked by commit count |
| `/profile` | Your GitHub profile summary |
| `/issues` | View, create and close GitHub Issues |
| `/releases` | View, create and delete repo releases |
| `/star <user/repo>` | Star any GitHub repository |
| `/stars` | Browse your starred repositories |

</details>

<details>
<summary><b>⚙️ Settings & Personalization</b></summary>

| Command | Description |
|---------|-------------|
| `/settings` | Bot personalization panel |
| `/privatemsg` | Customize the message shown to non-owners |
| `/savedpaths` | Manage favourite file path shortcuts |
| `/aliases` | Create custom command shortcuts |
| `/templates` | Manage commit message templates |

</details>

<details>
<summary><b>🛠️ Utility</b></summary>

| Command | Description |
|---------|-------------|
| `/status` | Full status: account, repo, branch, API health |
| `/ping` | Quick health check with response time |
| `/version` | Bot version and changelog |
| `/help` | Interactive help menu by category |
| `/cancel` | Cancel any in-progress action immediately |

</details>

---

## 🔒 Security

GitroHub handles OAuth tokens with **write access to your GitHub account**. Security is built in at every layer.

| 🛡️ Layer | Protection | Details |
|----------|------------|---------|
| **Encryption at rest** | AES-256-GCM | All GitHub tokens encrypted before writing to DB. Encryption key never stored in DB. |
| **Access control** | Single-owner | Only `TELEGRAM_ADMIN_ID` can use the bot. All others receive a private access message. |
| **No hardcoded secrets** | Env vars only | Zero credentials in source code. All secrets loaded from environment at runtime. |
| **Transport security** | HTTPS only | Railway enforces SSL. Webhook and OAuth callback reject plain HTTP connections. |
| **CSRF protection** | State token | Every OAuth flow generates a unique `state`. Callback validates before token exchange. |
| **Upload safety** | ZIP slip guard | All ZIP upload paths are sanitized, preventing path traversal (`../../etc/passwd`). |
| **Destructive actions** | Confirmation flows | File delete, repo delete, and logout require confirmation. Repo deletion uses a 3-step flow. |
| **Session isolation** | Per-account | Each GitHub account is an isolated encrypted session. Switching never leaks tokens. |
| **Token refresh** | Silent renewal | Sessions auto-refresh — you are never unexpectedly logged out mid-session. |

> [!IMPORTANT]
> Your GitHub OAuth token is never logged, never appears in error messages, and is never returned to Telegram in any form. Only the AES-256-GCM ciphertext ever touches the database.

---

## 🛠️ Tech Stack

| Library | Version | Role |
|---------|---------|------|
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | `20.7` | Async Telegram Bot framework (PTB v20) |
| [PyGithub](https://github.com/PyGithub/PyGithub) | `2.1.1` | GitHub REST API v3 client |
| [psycopg2-binary](https://pypi.org/project/psycopg2-binary/) | `2.9.9` | PostgreSQL database driver |
| [cryptography](https://cryptography.io/) | `41.0.7` | AES-256-GCM token encryption |
| [aiohttp](https://docs.aiohttp.org/) | `3.9.1` | Async HTTP server for webhook & OAuth callback |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | `1.0.0` | `.env` file loading for local development |
| [humanize](https://python-humanize.readthedocs.io/) | `4.9.0` | Human-readable file sizes and timestamps |
| [Pygments](https://pygments.org/) | `2.17.2` | Syntax highlighting for file content previews |
| [Pillow](https://python-pillow.org/) | `10.2.0` | Image processing utilities |

**Infrastructure:**

| Service | Role |
|---------|------|
| [Railway](https://railway.app) | Hosting, PostgreSQL, auto-deploy from GitHub |
| [GitHub API v3](https://docs.github.com/en/rest) | All GitHub operations |
| [Telegram Bot API](https://core.telegram.org/bots/api) | Messaging, inline buttons, webhook |

---

## ⚠️ Known Limitations

| Limitation | Details |
|-----------|---------|
| **GitHub API rate limit** | 5,000 requests/hour per authenticated user. Heavy batch operations or large repo mirrors consume multiple requests per file. |
| **File size cap** | Telegram bots cap file uploads at **50 MB**. Files or ZIPs over 50 MB cannot be uploaded through the bot. |
| **Binary file editing** | Binary files (images, executables, compiled assets) can be uploaded but cannot be previewed or edited inline in chat. |
| **Private repo access** | The bot accesses private repos only if the connected OAuth token was granted the `repo` scope — this is the default during login. |
| **Large repo ZIP mirror** | `/mirror` counts one API call per file. Repos with 1,000+ files may approach rate limits mid-commit. Use `/update` for large repos. |
| **No GitHub webhooks** | GitroHub does not yet listen for GitHub-side events (pushes, PR opens, CI results). This is on the roadmap. |
| **Message length** | File contents exceeding ~4,096 characters are truncated in the chat preview. Use `/download` for large files. |
| **Single admin** | Only one `TELEGRAM_ADMIN_ID` is supported per bot instance. Team/multi-user mode is on the roadmap. |

---

## 🗺️ Roadmap

> Planned features — not yet released.

**🔜 v1.3.0 — Workflow Automation**
- [ ] GitHub webhook listener — receive push, PR, and CI notifications in Telegram
- [ ] Scheduled commits — cron-style timer for recurring automated commits
- [ ] Auto-commit on file send — skip the commit message prompt entirely

**🔜 v1.4.0 — Pull Requests**
- [ ] View open pull requests with diff summaries
- [ ] Create pull requests between branches
- [ ] Merge and close PRs with a Telegram message as the merge comment
- [ ] Review and approve PRs

**🔜 v1.5.0 — Gists & Snippets**
- [ ] Create, view and edit GitHub Gists
- [ ] Share code snippets directly from Telegram chat

**💡 Backlog**
- [ ] GitHub Actions status viewer
- [ ] Dependabot alert summary
- [ ] Repository template support on repo creation
- [ ] Multiple Telegram admin IDs (team / shared mode)
- [ ] Inline mode for quick repo search without opening the bot chat

---

## 🚨 Troubleshooting

<details>
<summary><b>Bot doesn't respond to /start</b></summary>

- Check Railway deployment logs for startup errors
- Confirm `TELEGRAM_BOT_TOKEN` is correct and hasn't been revoked in BotFather
- Confirm `TELEGRAM_ADMIN_ID` exactly matches your numeric Telegram ID (get it from @userinfobot)
- Check the Railway service is running and not crashed

</details>

<details>
<summary><b>OAuth callback fails / "GitHub didn't return an access token"</b></summary>

- `WEBHOOK_URL` must be your exact Railway URL with **no trailing slash**
- Your GitHub OAuth App's callback URL must be exactly `https://your-app.railway.app/auth/github/callback`
- Both must match — a single extra character causes OAuth to reject the redirect

</details>

<details>
<summary><b>"❌ Not logged in" immediately after connecting</b></summary>

The `AES_ENCRYPTION_KEY` may have changed after sessions were stored. The encrypted tokens are now unreadable with the new key.

Fix: restore the original `AES_ENCRYPTION_KEY` in Railway variables. If the original key is lost, delete all rows from the `sessions` table and re-authenticate each account.

</details>

<details>
<summary><b>Database errors on startup</b></summary>

- Ensure the PostgreSQL plugin is added in Railway
- `DATABASE_URL` must be present (Railway injects this automatically when the plugin is added)
- `init_db()` runs on every startup and creates all tables — no manual SQL required

</details>

<details>
<summary><b>Webhook not receiving Telegram updates</b></summary>

Railway generates a new URL on each re-deploy unless you configure a custom domain. Whenever the URL changes:
1. Update `WEBHOOK_URL` in Railway variables
2. Update the GitHub OAuth App callback URL to match
3. Trigger a re-deploy

</details>

<details>
<summary><b>ZIP upload skips or misses files</b></summary>

- `/mirror` overwrites everything — all repo content is replaced by the ZIP contents
- `/update` only adds new files and modifies changed ones — unchanged files are skipped intentionally, and files deleted from the ZIP are **not** removed from the repo
- Files over 50 MB inside a ZIP are silently skipped due to Telegram's upload limit

</details>

---

## ❓ FAQ

**Q: Is GitroHub open source?**  
A: The bot is provided as a self-hostable package for personal use. See the [License](#️-license) section for full terms.

**Q: Can multiple people use the same bot instance?**  
A: By design, only the `TELEGRAM_ADMIN_ID` owner can use the bot. It's a personal GitHub remote control. Multi-admin / team mode is on the [roadmap](#️-roadmap).

**Q: Does GitroHub store my GitHub token?**  
A: Yes — encrypted with AES-256-GCM in your own PostgreSQL database that you fully control. The token never leaves your infrastructure in plaintext.

**Q: What GitHub OAuth scopes does GitroHub request?**  
A: The `repo` scope (full repository read/write) and `read:user` (username and profile). No email, no organization admin, no billing access is requested.

**Q: Can I use GitroHub with GitHub Enterprise?**  
A: Not currently — it targets `api.github.com`. GitHub Enterprise Server support is in the backlog.

**Q: What happens if I lose my `AES_ENCRYPTION_KEY`?**  
A: All stored sessions become permanently unreadable. Clear the `sessions` table and re-authenticate all accounts. Always back the key up securely outside of Railway.

**Q: Does the bot work if Railway puts my service to sleep?**  
A: Railway's free tier may sleep idle services. For always-on operation, upgrade to a Railway paid plan or configure the service as always-on.

**Q: Can I run it without Railway?**  
A: Yes — see [Local Development](#-local-development). Any server running Python 3.11+ and PostgreSQL works: VPS, Heroku, Render, Fly.io, or your own machine.

**Q: Is my data safe if someone finds my bot's Telegram username?**  
A: Yes. Anyone who isn't your `TELEGRAM_ADMIN_ID` receives only the custom private access message. They cannot trigger any commands, view any repos, or interact with any GitHub data.

---

## 📜 Changelog

### README v1.1 *(May 2026)*
- 🖼️ Added real screenshots — bot profile and live dashboard
- ⚡ Added Why GitroHub comparison table vs GitHub Web and Mobile
- 🎯 All feature sections now use collapsible `<details>` blocks
- 🗄️ Added full Database Schema section with annotated SQL
- 💻 Added Local Development guide with ngrok tip for OAuth
- ⚠️ Added Known Limitations table
- 🗺️ Added versioned Roadmap (v1.3 → v1.5 + backlog)
- 🚨 Troubleshooting now uses collapsible blocks instead of raw blockquotes
- ❓ Added FAQ section (9 questions)
- 🙏 Added Acknowledgements section
- ⚖️ Added License & Copyright section
- 📋 Commands reference now collapsible by category
- 🔔 GitHub native callouts (`[!NOTE]`, `[!WARNING]`, `[!TIP]`, `[!IMPORTANT]`)
- 🏷️ GitHub Topics added to footer for discoverability

### Bot v1.2.0 *(Apr 2026)*
- 🔗 "Connect GitHub Account" on `/start` is now a proper URL link button (↗)
- 🏠 Home button renders the full dashboard, not just text
- ✅ All inline buttons now respond: Stats, Log, Branches, Issues, Releases, Help, Download
- 📋 All help category sections fully wired
- ⬇️ Download by URL fully implemented
- 🔄 Batch commit confirm flow fixed end-to-end
- 🔍 Repo search from inline button working
- ⚙️ Repo Settings panel added
- 🐛 `do_batch_commit` / `do_zip_commit` implemented (were called but undefined)
- 🐛 `login_start` callback import error fixed

### Bot v1.1.0
- 👤 Multiple GitHub accounts per bot instance
- 🔄 One-tap account switching
- 🗑️ Clean account removal flow

### Bot v1.0.0 — Initial Release
- Full GitHub management via Telegram
- AES-256-GCM encrypted sessions
- ZIP mirror & update upload modes
- Interactive file browser with breadcrumbs
- Commit history, undo, and rollback
- Branch management & merging
- Issues, releases, stars, and profile
- Stats, traffic & contributor views
- Personalization settings & command aliases

---

## 🙏 Acknowledgements

GitroHub is built on the shoulders of these excellent open-source projects and services:

- **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** — The most complete async Telegram Bot library for Python
- **[PyGithub](https://github.com/PyGithub/PyGithub)** — Clean, well-maintained GitHub API v3 wrapper
- **[cryptography](https://cryptography.io/)** — Industry-standard Python cryptography primitives
- **[aiohttp](https://docs.aiohttp.org/)** — High-performance async HTTP client and server
- **[Railway](https://railway.app)** — Frictionless deployment and managed PostgreSQL
- **[Pygments](https://pygments.org/)** — Universal syntax highlighter
- **[humanize](https://python-humanize.readthedocs.io/)** — Human-friendly data formatting

Special thanks to the **[Telegram Bot API](https://core.telegram.org/bots/api)** and **[GitHub REST API v3](https://docs.github.com/en/rest)** teams for thorough public documentation.

---

## ⚖️ License

```
Copyright (c) 2026 GitroHub (@GitroHubBot)
All Rights Reserved.
```

This project is **proprietary software**. The source code is provided for personal, self-hosted use only.

**You may:**
- ✅ Deploy and run this bot for your own personal, non-commercial use
- ✅ Modify the code for your own private deployment
- ✅ Study the code for educational purposes

**You may not:**
- ❌ Redistribute this software or any modified version publicly
- ❌ Offer it as a public or commercial service to others
- ❌ Remove or alter copyright notices in any file
- ❌ Claim authorship of the original work

> For licensing inquiries, partnerships, or commercial use discussions, contact the author via Telegram: **[@GitroHub](https://t.me/GitroHub)**

---

<div align="center">

**Built with ❤️ by the GitroHub team**

<br/>

[![Telegram Bot](https://img.shields.io/badge/Bot-@GitroHubBot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/GitroHubBot)
[![Telegram Channel](https://img.shields.io/badge/Channel-@GitroHub-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://t.me/GitroHub)

<br/>

*Secure · Fast · Always in sync with GitHub*

---

*`telegram-bot` · `github-api` · `automation` · `dev-tools` · `git` · `github` · `bot-development` · `devops` · `productivity` · `gitops` · `developer-tools` · `automation-tools` · `software-development` · `cloud-tools` · `api`*

</div>
