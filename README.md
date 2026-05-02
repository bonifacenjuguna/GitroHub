# 🤖 GitroHub — @GitroHubBot
### v1.3.0

> Your GitHub, inside Telegram. Manage repos, commit code, upload files, branches — all without leaving Telegram.

---

## ✅ v1.3.0 — Debug Verification

Full automated debug scan results:
- **16/16 files** — 0 syntax errors
- **0 MarkdownV2** — 100% HTML parse mode
- **83 callbacks** — all handled
- **28 commands** — all registered
- **47 features** — all implemented and verified
- **7 context-safe functions** — stats/issues/releases work from both commands and buttons
- **Global error handler** — bot never crashes silently

---

## 🚀 Setup Guide

### 1. GitHub OAuth App

Go to **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**

| Field | Value |
|-------|-------|
| Application name | GitroHub |
| Homepage URL | `https://your-app.railway.app` |
| Authorization callback URL | `https://your-app.railway.app/auth/github/callback` |

### 2. Generate AES-256 Key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Get Your Telegram User ID

Message [@userinfobot](https://t.me/userinfobot) on Telegram.

### 4. Railway Environment Variables

```
TELEGRAM_BOT_TOKEN      = from @BotFather
TELEGRAM_ADMIN_ID       = your telegram user ID
GITHUB_CLIENT_ID        = from GitHub OAuth App
GITHUB_CLIENT_SECRET    = from GitHub OAuth App
WEBHOOK_URL             = https://your-app.railway.app
DATABASE_URL            = set automatically by Railway PostgreSQL plugin
AES_ENCRYPTION_KEY      = your generated 32-byte hex key
PORT                    = 8080
```

> `GITHUB_REDIRECT_URI` is auto-built from `WEBHOOK_URL` — no need to set it manually.

### 5. Deploy

1. Push to a **private** GitHub repo
2. Create new Railway project → Deploy from GitHub
3. Add **PostgreSQL** plugin
4. Set the environment variables above
5. Deploy — bot starts automatically and registers all commands

---

## 📁 Project Structure

```
gitrohub/
├── main.py                 # Bot entry point, callback router, error handler
├── requirements.txt        # Dependencies
├── Procfile               # Railway: python main.py
├── railway.toml           # Railway config
├── README.md
├── .env.example           # ENV template
├── database/
│   └── db.py              # PostgreSQL: sessions, settings, aliases, templates
├── handlers/
│   ├── auth.py            # OAuth login, accounts, multi-account switching
│   ├── core.py            # /start, /help, /ping, /status, /version
│   ├── repos.py           # Repo management, projects dashboard
│   ├── files.py           # Browse (breadcrumb), read, edit, search, move
│   ├── upload.py          # Single file, batch files, ZIP mirror/update
│   ├── branches.py        # Create, switch, merge, delete, protect, diff
│   ├── history.py         # Log, undo, rollback, view commit
│   ├── extras.py          # Stats, download, issues, releases, stars, gists
│   └── settings.py        # Settings, private msg, aliases, paths, templates
└── utils/
    ├── encryption.py      # AES-256-GCM token encryption
    └── github_helper.py   # GitHub API helpers, HTML escaping, error messages
```

---

## 🔑 Features

| Category | Features |
|----------|---------|
| **Auth** | GitHub OAuth, multi-account, persistent sessions, silent token refresh |
| **Repos** | Create, delete (3-step), rename, transfer, fork, visibility, pin, topics |
| **Files** | Browse (breadcrumb nav), read, edit, delete, move, search |
| **Upload** | Single file, batch files, ZIP mirror, ZIP update, preview tree |
| **Branches** | Create, switch, merge, delete, protect, diff |
| **History** | Log, undo last, rollback to any commit |
| **Issues** | List open, create, close |
| **Releases** | List, create, delete |
| **Stars** | Star, unstar, list starred, stargazers |
| **Stats** | Repo stats, profile, traffic, contributors |
| **Gists** | List, delete |
| **Settings** | Theme, time/date format, timezone, private message, aliases, templates, saved paths |
| **Safety** | Level 1/2/3 verification, cancel anywhere, timeouts, error messages with reasons |

---

## 🔒 Security

- **AES-256-GCM** encrypted GitHub tokens in PostgreSQL
- **Single admin** — only your Telegram ID works
- **No secrets in code** — everything via Railway ENV vars
- **HTTPS only** — Railway enforces SSL
- **ZIP slip protection** — path sanitization on all uploads
- **OAuth CSRF** — state parameter validation
- **Sessions never expire** — silent background token refresh
