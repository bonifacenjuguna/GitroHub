# 🚀 Deployment Guide — GitroHub on Railway

This guide walks through deploying GitroHub from a clean Railway project to a
fully working, owner-only Telegram bot.

---

## 1. Prerequisites

- A [Railway](https://railway.app) account
- A Telegram account (to create the bot via [@BotFather](https://t.me/BotFather))
- A GitHub account (to create an OAuth App)
- Your Telegram numeric user ID (get it from [@userinfobot](https://t.me/userinfobot))

---

## 2. Create the Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram.
2. Send `/newbot`, choose a display name, then a username ending in `bot`
   (e.g. `GitroHubBot`).
3. BotFather returns a **bot token** — save it, you'll need it as `BOT_TOKEN`.
4. **Do not** run `/setcommands` — this project intentionally keeps all
   commands hidden from Telegram's autocomplete menu (see README).

---

## 3. Create the GitHub OAuth App

1. Go to **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
   (`https://github.com/settings/developers`).
2. Fill in:
   - **Application name:** GitroHub
   - **Homepage URL:** `https://gitrohub.vercel.app` (or your domain)
   - **Authorization callback URL:** `https://gitrohub.vercel.app/oauth/github/callback`
     — must match your `DOMAIN` env var **exactly**, including no trailing slash.
3. Save, then generate a **Client Secret**.
4. Note the **Client ID** and **Client Secret** — you'll need these as
   `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET`.

---

## 4. Create the Railway Project

1. Create a new Railway project → **Deploy from GitHub repo** (push this
   project to a **private** GitHub repository first, or use Railway CLI to
   deploy directly from your machine without pushing to GitHub at all).
2. Add a **PostgreSQL** plugin to the project — Railway automatically
   injects `DATABASE_URL`.
3. Add a **Redis** plugin to the project — Railway automatically injects
   `REDIS_URL`.
4. Under your service's **Settings → Networking**, generate a public
   domain (or attach your custom domain, e.g. `gitrohub.vercel.app` via a
   CNAME if using Railway alongside a separate DNS provider — note:
   despite the `.vercel.app`-style domain used throughout this project's
   design, the bot itself runs on Railway; point your domain's DNS at
   Railway's provided target).

---

## 5. Set Environment Variables

In Railway's **Variables** tab, add every value from `.env.example`:

```
BOT_TOKEN=
BOT_USERNAME=GitroHubBot
BOT_OWNER_ID=
BOT_OWNER_USERNAME=
BOT_OWNER_NAME=
DOMAIN=https://gitrohub.vercel.app
WEBHOOK_SECRET=
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
ENCRYPTION_MASTER_KEY=
NODE_ENV=production
LOG_LEVEL=info
```

`DATABASE_URL` and `REDIS_URL` are injected automatically by their
respective Railway plugins — you don't need to set these manually.

### Generating secrets

Run these locally (Node.js required) to generate secure values:

```bash
# WEBHOOK_SECRET
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# ENCRYPTION_MASTER_KEY
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

---

## 6. Deploy

Railway will automatically:
1. Detect the Node.js project via Nixpacks.
2. Run `npm install`.
3. Run the `start` command defined in `railway.json`:
   `npm run migrate && npm start`
   — this applies the Postgres schema (safe to run repeatedly — every
   statement is `CREATE TABLE IF NOT EXISTS`), then starts the bot.

On successful boot, the bot automatically registers its own Telegram
webhook pointed at `${DOMAIN}/telegram/webhook` — **no manual webhook
setup needed.**

---

## 7. Verify

1. Visit `https://your-domain/health` — should return `{"status":"ok", ...}`.
2. Message your bot on Telegram with `/start` (using the Telegram account
   whose ID matches `BOT_OWNER_ID`) — you should see the welcome screen.
3. Send `/ping` — should reply within a second or two with latency figures.
4. Send `/health` — full diagnostic of Postgres/Redis connectivity.

If nothing responds: check Railway's deploy logs for the specific error —
the bot fails fast and loudly on misconfiguration (see `src/config/env.js`).

---

## 8. Connecting Your GitHub Account

1. In the bot, go to **🔐 Account & Security → 🔗 Connect GitHub**.
2. Tap through to GitHub's authorization screen.
3. Approve access.
4. You'll land on the animated GitroHub callback page, then be redirected
   back into Telegram automatically.

---

## 9. Updating / Redeploying

Railway redeploys automatically on every push to your connected branch
(if using GitHub-connected deploys), or via `railway up` if using the CLI.
The migration step re-runs safely on every deploy — no manual migration
management needed for this project's schema.

---

## 10. Rotating Secrets

If you ever need to rotate `ENCRYPTION_MASTER_KEY`: **all previously
encrypted tokens become unreadable** the moment you change it. You'll
need to disconnect and reconnect GitHub after rotating this value. Plan
accordingly — this is not a zero-downtime rotation for existing
connections.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Bot doesn't respond at all | `BOT_OWNER_ID` doesn't match your Telegram ID — check with `/start` from the correct account |
| "Database not migrated" on boot | Migration step didn't run — check Railway build logs |
| OAuth callback shows an error page | `GITHUB_OAUTH_CLIENT_ID`/`SECRET` mismatch, or callback URL doesn't exactly match what's registered on GitHub |
| `/health` shows Redis or Postgres unreachable | Plugin not attached to the service, or `DATABASE_URL`/`REDIS_URL` not injected — check Railway's Variables tab |
