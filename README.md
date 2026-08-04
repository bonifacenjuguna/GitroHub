<div align="center">

<img src="./public/logo.png" width="140" alt="GitroHub logo" />

<h1>GitroHub</h1>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&pause=1000&color=3B82F6&center=true&vCenter=true&width=460&lines=GitHub+from+Telegram;Create+%C2%B7+Upload+%C2%B7+Download+%C2%B7+Manage;Owner-only+%C2%B7+No+one+else+gets+in;Built+with+Telegraf.js+%2B+Octokit" alt="Typing SVG" />

<p>
<img src="https://img.shields.io/badge/version-0.2.0-3B82F6?style=for-the-badge" />
<img src="https://img.shields.io/badge/node-%3E%3D18-3B82F6?style=for-the-badge&logo=node.js&logoColor=white" />
<img src="https://img.shields.io/badge/JavaScript-No%20TypeScript-F1E05A?style=for-the-badge&logo=javascript&logoColor=black" />
<img src="https://img.shields.io/badge/hosted%20on-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white" />
<img src="https://img.shields.io/badge/license-MIT-38BDF8?style=for-the-badge" />
</p>

</div>

---

## What is GitroHub?

GitroHub is a **private, owner-only Telegram bot** that connects to your GitHub account and lets you create, browse, edit, upload to, and delete repositories — all from a Telegram chat, on your phone, without opening a browser.

This isn't a public bot. It's built to talk to **exactly one person** (you) — the number in `OWNER_ID`. Everyone else who messages it is silently ignored, no reply, no logging, no processing, ever.

---

## ✨ Features

| | |
|---|---|
| 🔗 **OAuth Web Flow** | Tap once → browser opens → authorize → auto-redirected back with an animated confirmation page |
| 📁 **Repo Management** | List, filter, sort, search (fuzzy), create, rename, delete, toggle visibility |
| ⬆️ **Upload** | Single file or `.zip` (auto-strips the GitHub-style wrapper folder), with 🆕 New / ✏️ Modified / ➖ Unchanged detection before committing |
| 📂 **Browse Files** | Full tree navigation, view content, send as file, edit inline, delete |
| ⬇️ **Download** | Any of your repos, or any public external repo pasted as a link |
| 🍴 **Fork** | Fork any public GitHub repo straight into your account |
| ⚙️ **Settings** | Live Postgres/Redis health, GitHub rate-limit status, memory/uptime, bot version |
| 📜 **Activity Log** | Every action recorded, filterable to errors-only |
| 🔔 **Notifications** | Granular on/off per category |
| 🎨 **Animated OAuth Page** | Custom callback page with particle background, circuit-line animation, live status feed, and a countdown auto-redirect back into Telegram |

---

## 🏗️ Architecture

```
┌─────────────────┐        ┌──────────────────────┐
│   Telegram       │◄──────►│   bot.js (Telegraf)   │
│   (You, only)    │        │   Owner gate → Scenes │
└─────────────────┘        └──────────┬────────────┘
                                       │
                     ┌─────────────────┼─────────────────┐
                     ▼                 ▼                 ▼
              ┌────────────┐   ┌─────────────┐   ┌──────────────┐
              │  Postgres   │   │    Redis     │   │  GitHub API   │
              │ users, logs │   │ sessions,    │   │ (Octokit)     │
              │             │   │ wizard state │   │              │
              └────────────┘   └─────────────┘   └──────────────┘
                                       ▲
                                       │
                     ┌─────────────────┴─────────────────┐
                     │   app.js (Express) — /callback      │
                     │   Animated OAuth confirmation page   │
                     └──────────────────────────────────────┘
```

**One process, two jobs**: the same Node process runs both the Telegraf bot (webhook or polling) and a small Express server that only exists to handle GitHub's OAuth redirect (`/callback`) and serve the animated confirmation page. This keeps Railway hosting to a single service.

### Folder structure

```
gitrohub/
├── public/
│   ├── logo.png              # Bot logo (transparent PNG)
│   └── callback.html         # Animated OAuth callback page
├── src/
│   ├── index.js               # Entrypoint — boots DB, Redis, bot, server
│   ├── bot.js                 # Telegraf wiring: middleware, scenes, routers
│   ├── config.js               # Env var loading + validation
│   ├── db/
│   │   ├── postgres.js         # Pool + ping()
│   │   ├── redis.js            # Client + ping()
│   │   ├── schema.sql          # users, activity_log tables
│   │   └── migrate.js          # Runs schema.sql on boot
│   ├── lib/
│   │   ├── github.js           # Octokit wrapper — every GitHub operation
│   │   ├── oauth.js            # Authorize URL + code exchange
│   │   ├── users.js            # Account data-access (connect/disconnect)
│   │   ├── crypto.js           # AES-256-GCM token encryption
│   │   ├── gitHash.js          # Git blob SHA (for upload change-detection)
│   │   ├── activity.js         # Activity log read/write
│   │   ├── session.js          # Redis-backed wizard state (Back/Cancel)
│   │   ├── format.js           # Locked formatting standard (see below)
│   │   └── requireConnected.js # Guard used by every GitHub-touching handler
│   ├── middleware/
│   │   ├── ownerGate.js        # Silently drops all non-owner traffic
│   │   └── redisSessionStore.js
│   ├── keyboards/
│   │   ├── bbtb.js             # Reply keyboards (Buttons Below Typing Bar)
│   │   └── inline.js           # Inline keyboards
│   ├── handlers/                # One file per screen/zone
│   └── scenes/                  # Multi-step wizards (Create/Upload/Rename/Edit)
├── package.json
├── .env.example
└── README.md
```

---

## 📋 Changelog

### v0.2.0 — Real-world testing fixes
A big pass of fixes based on hands-on testing against a live account:

- **Fixed:** Download Repo (and external repo download) produced an empty 9-byte zip for any private repo — the code was fetching an unauthenticated `github.com/.../archive/...zip` URL, which 404s without a session for private repos. Now uses Octokit's authenticated archive endpoint, works for private and public repos alike.
- **Fixed:** Repo list showed a single guessed "primary language" with an emoji circle. Now shows a real top-3 language breakdown with percentages (`GET /repos/{owner}/{repo}/languages`), and repos are visually separated with divider lines instead of running together.
- **Fixed:** Tapping ↕️ Sort or 🔎 Filter crashed with `400: message can't be edited` — these were trying to edit a message that didn't exist from that context (a BBTB tap has no prior bot message attached to edit). Now they send their own fresh message, edit *that*, briefly show a confirmation, auto-delete it, then send a fresh repo list.
- **Fixed (structural):** Any BBTB button or even `/start` got silently swallowed while inside a wizard (Create Repo, Upload, Rename, Edit File) — Telegraf hands control entirely to the active scene, so handlers registered afterward never ran. Fixed by attaching the exact same navigation handlers directly onto every scene as first-class escape hatches, so `/start`, `/cancel`, and every BBTB nav button now work identically whether or not a wizard is active.
- **Fixed:** "⬆️ Upload Files" button (shown on empty repos and after creating a new repo) did nothing — its callback pattern was never wired up in the router.
- **Fixed:** Repo deletion failed with "Must have admin rights to Repository" — the OAuth scope only requested `repo`, not `delete_repo`. Scope now requests both. **You'll need to disconnect and reconnect once** for this to take effect on an already-linked account.
- **Fixed:** Uploading a photo via Telegram's image picker failed with a generic "send a document" message — now explicitly explains photos get compressed (altering file bytes) and tells you to use the 📎 File option instead.
- **Fixed:** Typing a manual upload path had an unreachable "(leave blank for root)" instruction — Telegram doesn't allow sending empty text. Added an explicit "📍 Use Root" button instead.
- **Improved:** Before asking for a manual upload path, the bot now shows the repo's current top-level file/folder structure for context.
- **Improved:** Upload change-detection now shows exact size deltas for modified files (e.g. `helper.js: 2.1 KB → 2.4 KB`), and refuses outright with a clear message — no Commit button offered at all — when nothing actually changed, instead of allowing a no-op commit.
- **New:** Bot commands (`/start`, `/settings`, `/cancel`) now register automatically via `setMyCommands` on boot — no manual BotFather setup needed.
- **New:** Distinct disconnected-state flow — BBTB now shows only "🔗 Connect GitHub" and "⚙️ Settings" while logged out (instead of the full menu with dead buttons underneath), and Settings shows clear "Not connected" placeholders instead of blank/broken GitHub-dependent fields. Disconnecting now resets the BBTB immediately.
- **Improved:** Welcome-back message now shows your GitHub username as `@username` and includes a live repo count.

### v0.1.1 — Bug fix
- **Fixed:** inline keyboards were being silently dropped on 7 screens due to a `reply_markup` conflict between inline and BBTB keyboards sharing one message.

### v0.1.0 — Initial build
- Owner-only gate, OAuth Web Flow with animated callback page, My Repos, Create/Rename/Delete repo, Visibility toggle, Upload, Browse Files, Download, Fork, Settings dashboard, Activity Log, Notifications.

---

## 🚀 Setup

### 1. Create the Telegram bot
Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow the prompts → copy the token.

### 2. Get your Telegram user ID
Message [@userinfobot](https://t.me/userinfobot) → copy your numeric ID. This becomes `OWNER_ID` — the **only** ID the bot will ever respond to.

### 3. Create a GitHub OAuth App
Go to [github.com/settings/developers](https://github.com/settings/developers) → **New OAuth App**:
- **Homepage URL**: your Railway URL (e.g. `https://gitrohub-production.up.railway.app`)
- **Authorization callback URL**: `https://your-railway-url.up.railway.app/callback` *(must match exactly, no trailing slash)*

Copy the **Client ID** and generate a **Client Secret**.

### 4. Set up Railway
1. Create a new Railway project, deploy from this repo (or upload the zip)
2. Add a **Postgres** plugin — copies `DATABASE_URL` into your environment automatically
3. Add a **Redis** plugin — copies `REDIS_URL` into your environment automatically
4. Set the remaining environment variables (copy `.env.example` → fill in):

```
BOT_TOKEN=...
OWNER_ID=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
BASE_URL=https://your-railway-url.up.railway.app
SESSION_JWT_SECRET=$(openssl rand -hex 32)
TOKEN_ENCRYPTION_KEY=$(openssl rand -hex 32)
NODE_ENV=production
```

5. Deploy. On boot, GitroHub automatically:
   - Runs the Postgres migration (creates `users` + `activity_log` tables — safe to re-run)
   - Connects to Redis
   - Registers the Telegram webhook pointing at `${BASE_URL}/telegram-webhook`
   - Starts the Express server for `/callback`

### 5. Local development (optional)
```bash
npm install
cp .env.example .env   # fill in your values, leave NODE_ENV unset
npm run dev             # runs in long-polling mode, no webhook needed
```
In dev mode the bot polls Telegram directly, so `BASE_URL` only needs to be reachable for the `/callback` route — use a tool like `ngrok http 3000` and point your GitHub OAuth App + `.env`'s `BASE_URL` at the ngrok URL.

### 6. Talk to your bot
Open your bot on Telegram, hit `/start`, tap **Connect GitHub Account** — you'll get the animated callback page, then land back in the bot fully connected.

---

## 🎨 The animated OAuth callback page

`public/callback.html` is a single self-contained file (no build step, no framework) featuring:
- A canvas-based particle field + circuit-line background with a traveling signal pulse
- A slowly rotating conic gradient glow behind the card
- A terminal-style status feed that plays out step-by-step with SVG checkmarks/X's (no emoji — Lucide-style hand-drawn stroke icons)
- A live SVG countdown ring that auto-redirects back into Telegram (deep link) when it hits zero
- Distinct color themes for success (blue → green) and failure (blue → red) states

The bot's `app.js` injects `window.__GITROHUB__` with the real outcome (`success`/`error`, GitHub username, and — on failure — exactly which step failed) so the page always reflects what actually happened, never a generic animation.

---

## 🔒 Security notes

- **Owner gate is the first middleware registered**, before session lookup, before anything — non-owner messages are dropped with zero processing, zero reply, zero log noise.
- GitHub access tokens are encrypted at rest with **AES-256-GCM** (`TOKEN_ENCRYPTION_KEY`) before being stored in Postgres — never stored in plaintext.
- OAuth `state` parameter is a short-lived **signed JWT** carrying your Telegram ID, so the `/callback` route can't be spoofed into linking a token to the wrong chat.
- OAuth scope requested is `repo` only — full control of repositories, nothing broader (no `admin:org`, no `user` scope, etc.).

---

## 📐 Design principles baked into the code

These were locked in during design and apply everywhere in the codebase:

1. **BBTB vs Inline** — reusable/frequent actions live in the Reply Keyboard (bottom bar); content-specific and destructive/final actions live inline, attached to the message.
2. **Every error names the exact cause + next step** — see `format.errorMessage()`, used everywhere instead of generic "Something went wrong" messages.
3. **State-based emoji/labels are never stale** — visibility, language, filter/sort labels are recomputed fresh on every render.
4. **Edit in place within a flow, send fresh on final/destructive outcomes** — so multi-step wizards don't spam the chat, but a completed action always leaves a permanent record.
5. **⬅️ Back ≠ restart** — wizard state lives in Redis (`WIZARD_SESSION_TTL_SECONDS`, default 30 min), so backing up a step preserves what you already typed, and a Railway restart mid-flow doesn't wipe your progress.

---

## ⚠️ Known limitations in this v0.2.0 build

Being upfront about what's simplified, consistent with the "specific errors, not vague ones" principle applied to the docs too:

- **⚠️ IMPORTANT — reconnect required:** v0.2.0 adds the `delete_repo` scope needed to actually delete repositories. If you connected under v0.1.x, repo deletion will keep failing with "Must have admin rights" until you **Disconnect and reconnect once** from Settings — this re-runs the OAuth flow under the new scope.
- **"Browse Folders" during single-file upload path selection** still falls back to type-path (with the repo's current structure now shown for context, and a one-tap Root shortcut) — the folder-tap navigator for *choosing* an upload destination wasn't wired up in this pass. Browsing an *existing* tree (Browse Files) is fully implemented.
- **GitHub webhook-based notifications** (stars/issues/PRs) are schema-ready but the receiving webhook endpoint isn't implemented yet — deferred v1.1+ item.
- **🟢🟡🔴 Activity Status indicator** and **🍴 "Forked from X" tag** were explicitly deferred to a future version during design.
- **Text/slash-command fallback** for repo actions (e.g. `/repos`) isn't implemented — `/start`, `/settings`, `/cancel` now exist as commands, but the button-driven UI remains the primary interface for everything else.
- Destructive-action **double-tap debouncing** relies on Telegram's own callback-query semantics, no explicit server-side idempotency lock yet — low risk for a single-user bot, worth hardening before wider use.

None of these block normal daily use.

---

## 💡 Recommendations for what's next

A few things worth considering that came up while building, beyond what was in the original design conversation:

1. **Rate-limit-aware backoff** — right now if GitHub's API rate limit is hit mid-operation, the user gets a clear error (per design), but the bot doesn't automatically queue/retry after the reset window. Worth adding for upload-heavy sessions.
2. **Large repo tree pagination** — `getTree()` fetches the *entire* recursive tree in one call, which is fine up to a few thousand files, but very large repos (10k+ files) could hit response-size or Telegram-message-size limits in Browse Files. Worth capping and paginating server-side, not just visually.
3. **Webhook signature verification** — when the GitHub-activity webhook endpoint gets built (deferred item), it must verify GitHub's `X-Hub-Signature-256` header against a shared secret, or anyone who finds the URL could inject fake "activity" into your Activity Log.
4. **Structured logging** — `console.log`/`console.error` is fine for a single-user bot on Railway's log viewer, but if this ever grows, swapping in a tiny structured logger (pino is lightweight and pairs well with Railway's log parsing) would make the Settings → Activity error surfacing more powerful.
5. **Health check endpoint** — Railway can auto-restart on failed health checks; a simple `GET /health` that checks Postgres + Redis + returns 200/503 would let Railway catch a degraded state before you notice it manually in Settings.

---

<div align="center">
<sub>Built for one person, on purpose. 🔒</sub>
</div>
