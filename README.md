# 🤖 GitroHub — @GitroHubBot

> Your GitHub, inside Telegram. Manage repos, commit code, upload files & branches — all without leaving Telegram.

---

## 🚀 Setup Guide

### Step 1 — Prerequisites
- Python 3.11+
- Railway.app account
- GitHub account
- Telegram Bot Token (from @BotFather)

---

### Step 2 — GitHub OAuth App

1. Go to **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
2. Fill in:
   - **Application name:** GitroHub
   - **Homepage URL:** `https://your-app.railway.app`
   - **Authorization callback URL:** `https://your-app.railway.app/auth/github/callback`
3. Click **Register application**
4. Copy your **Client ID** and **Client Secret**

---

### Step 3 — Generate Your AES-256 Key

Run this once in your terminal:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output — this is your `AES_ENCRYPTION_KEY`.

---

### Step 4 — Get Your Telegram User ID

Message [@userinfobot](https://t.me/userinfobot) on Telegram.
It will reply with your user ID — copy it.

---

### Step 5 — Deploy on Railway

1. Push this code to a **private** GitHub repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Add a **PostgreSQL** plugin to your project
4. Set these **Environment Variables** in Railway:

```
TELEGRAM_BOT_TOKEN      = your_bot_token_from_botfather
TELEGRAM_ADMIN_ID       = your_telegram_user_id
GITHUB_CLIENT_ID        = your_github_oauth_client_id
GITHUB_CLIENT_SECRET    = your_github_oauth_client_secret
GITHUB_REDIRECT_URI     = https://your-app.railway.app/auth/github/callback
WEBHOOK_URL             = https://your-app.railway.app
AES_ENCRYPTION_KEY      = your_generated_32_byte_hex_key
DATABASE_URL            = (Railway fills this automatically)
PORT                    = 8080
```

5. Deploy — Railway will build and start the bot automatically

---

### Step 6 — BotFather Setup

Send these to [@BotFather](https://t.me/BotFather):

```
/setdescription
@GitroHubBot
Manage your GitHub directly from Telegram.
Repos, commits, branches & more. 🚀
```

```
/setabouttext
@GitroHubBot
Full GitHub management from Telegram.
Commit, push and control your workflow ⚙️
```

Upload your GitroHub logo as the bot's profile picture.

> ⚠️ Don't set commands manually in BotFather — the bot registers all commands automatically on startup.

---

## 📁 Project Structure

```
gitrohub/
├── main.py                 # Bot entry point + callback router
├── requirements.txt        # Python dependencies
├── Procfile               # Railway start command
├── railway.toml           # Railway config
├── .env.example           # Environment variables template
├── database/
│   ├── __init__.py
│   └── db.py              # PostgreSQL models & helpers
├── handlers/
│   ├── __init__.py
│   ├── auth.py            # Login, logout, accounts, OAuth
│   ├── core.py            # Start, help, ping, status, version
│   ├── repos.py           # Repo management, projects, dashboard
│   ├── files.py           # Browse, read, edit, delete, search
│   ├── upload.py          # Single file, batch, ZIP upload
│   ├── branches.py        # Branch management, merge, diff
│   ├── history.py         # Log, undo, rollback
│   ├── extras.py          # Stats, profile, download, issues, releases, stars
│   └── settings.py        # Settings, private message, aliases, paths
└── utils/
    ├── __init__.py
    ├── encryption.py      # AES-256-GCM token encryption
    └── github_helper.py   # GitHub API helpers & error messages
```

---

## 🔒 Security

- **AES-256-GCM** encryption on all GitHub tokens
- **Single admin** — only your Telegram ID can use the bot
- **Environment variables** — no secrets in code
- **HTTPS only** — Railway enforces SSL
- **ZIP slip protection** — path sanitization on all uploads
- **OAuth CSRF protection** — state parameter validation
- **Silent token refresh** — sessions never expire

---

## ⚡ Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome & quick start |
| `/login` | Connect GitHub account |
| `/projects` | Your active working repos |
| `/repos` | All repos on your GitHub |
| `/create` | Create a new repo |
| `/use <repo>` | Switch active repo |
| `/upload <path>` | Upload a single file |
| `/batch` | Upload multiple files |
| `/mirror` | ZIP upload (full mirror) |
| `/update` | ZIP upload (add & modify) |
| `/browse` | Browse repo files |
| `/read <file>` | Read file contents |
| `/edit <file>` | Edit file in chat |
| `/download` | Download repo as ZIP |
| `/clone <url>` | Clone any repo |
| `/branch` | Manage branches |
| `/log` | Commit history |
| `/undo` | Reverse last commit |
| `/diff <b1> <b2>` | Compare branches |
| `/stats` | Repo statistics |
| `/profile` | GitHub profile |
| `/settings` | Personalization |
| `/ping` | Check bot status |
| `/cancel` | Cancel current action |

---

## 🛠️ Built With

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [PyGithub](https://github.com/PyGithub/PyGithub)
- [PostgreSQL](https://www.postgresql.org/)
- [Railway](https://railway.app/)
- [cryptography](https://cryptography.io/)

---

Made with ❤️ — GitroHub @GitroHubBot
