<div align="center">

<img src="./public/logo.png" width="140" alt="GitroHub logo" />

<h1>GitroHub</h1>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&pause=1000&color=3B82F6&center=true&vCenter=true&width=460&lines=GitHub+from+Telegram;Create+%C2%B7+Upload+%C2%B7+Download+%C2%B7+Manage;Owner-only+%C2%B7+No+one+else+gets+in;Built+with+Telegraf.js+%2B+Octokit" alt="Typing SVG" />

<p>
<img src="https://img.shields.io/badge/version-0.6.0-3B82F6?style=for-the-badge" />
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
| 📌 **Pinned Repos** | Manual quick-access list with drag-style reorder (⬆️⬇️), independent of GitHub |
| 🏷️ **Tags** | Your own labels across repos — filter by tag, bulk-select by tag, shown as chips everywhere a repo appears |
| 🧹 **Bulk Repo Actions** | Multi-select repos (with smart shortcuts: stale, private, public, by tag) and delete/visibility/download them all in one pass, with live progress and honest per-item failure reporting |
| 📥 **Batch Upload** | Collect several loose files before committing — one combined commit, one combined New/Modified/Unchanged summary |
| 🔁 **Replace** | Swap a single file's content by sending a new file (not retyping), or fully sync a folder (add/update/delete) with an explicit before-you-commit delete preview |
| ⬆️ **Upload Here** | Upload directly into whatever folder you're currently browsing, path pre-filled |
| ⚙️ **My Defaults** | Saved visibility/commit-message/upload-path/sort/filter defaults, with a "learn from me" pattern nudge |
| 📦 **Storage & Data** | See what GitroHub remembers about you, clear it granularly (or fully, with a typed confirmation), export it, and auto-cleanup old activity |
| 🔑 **Access Log** | Security-focused connection history, separate from general Activity |

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

> Upgrading from an older version? Just deploy — `migrate.js` re-runs `schema.sql` on every boot using `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` throughout, so new tables and columns (pins, tags, defaults, etc.) get added automatically without touching your existing data.

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

**v0.3.0 additions**, all following the same `lib/` = data access, `handlers/` = screen logic split:
`lib/pins.js`, `lib/tags.js`, `lib/defaults.js`, `lib/pathMemory.js`, `lib/accessLog.js`, `lib/dataStore.js`, `handlers/pinned.js`, `handlers/tags.js`, `handlers/bulkActions.js`, `handlers/myDefaults.js`, `handlers/storageData.js`, `handlers/accessLogScreen.js`. No new scenes were needed — every new feature reuses the existing wizard/session patterns.

---

## 🧠 Memory & stability (Railway free tier)

Railway's free/trial tier caps each service at **512MB RAM**. Node's V8 engine doesn't know that by default — it sizes its heap based on what it *thinks* the machine has, so without help it grows past the container's real limit and gets hard-killed by the kernel (`Killed` in the logs, no stack trace, since Node never gets a chance to log anything).

GitroHub now defends against this on three layers:

1. **`--max-old-space-size=384`** (set in `package.json`'s start script) forces V8 to respect a real ceiling and garbage-collect proactively, instead of growing unchecked. Leaves ~128MB headroom under the 512MB limit for buffers and native overhead that live outside V8's heap.
2. **A self-imposed RSS watchdog** (`MEMORY_WATCHDOG_MB`, default 400) checks actual memory every 30s and triggers a *clean* shutdown — closing Postgres and Redis properly — before the kernel ever needs to force-kill it. Railway restarts either way; this just avoids any risk of a write getting cut off mid-flight.
3. **File content no longer round-trips through Redis.** During Upload, raw file bytes used to live in the Telegraf wizard state, which gets serialized to Redis on every single step — for a near-1MB zip, that meant repeatedly re-serializing significant payloads. Content now lives in a short-lived in-process cache (`lib/fileBufferCache.js`); only a lightweight reference goes into session state.

Also tightened: the Postgres pool is capped at `PG_POOL_MAX` (default 3, was unbounded up to 10) — a single-owner bot doesn't need more — and GitHub API clients are cached per token instead of being constructed fresh on every single call.

If you're still seeing crashes after deploying this version, check `GET /health` (see below) and Railway's Metrics tab — if RSS is climbing steadily even at rest, that points to something new rather than the causes above.

### `GET /health`
Returns `200` with `{ status: "ok", postgres, redis, memoryMB, uptimeSeconds }` when healthy, `503` with `status: "degraded"` if either DB is unreachable. Point Railway's health check at this path so it can restart a degraded instance proactively instead of only reacting after a crash.

---

## 📋 Changelog

### v0.6.0 — Optimization, hardening, and a real security fix
A large pass covering performance, resilience, and a genuine security gap — all discussed and locked in before building.

**Security (do this one):**
- **Fixed:** the Telegram webhook accepted any POST request without verifying it actually came from Telegram. Since `ownerGate` trusts whatever `from.id` is in the request body, a forged request claiming to be the owner would have gone straight through — full bot control, no Telegram account needed. Now verified via Telegram's `secret_token` mechanism on every incoming webhook request. **Set `TELEGRAM_WEBHOOK_SECRET`** in Railway (falls back to a derived value if unset, but a dedicated secret is strongly recommended for a public URL).

**Performance:**
- **New:** short-lived caching (60s) for repo lists and per-repo language breakdowns, plus a longer-lived cache (10min) for your GitHub username — My Repos, Pinned, Bulk Select, and Search were all independently re-fetching the same data within seconds of each other. Every write path (create/delete/rename/upload/visibility/bulk actions/disconnect) explicitly invalidates the relevant cache, so nothing goes stale.
- **Fixed:** GitHub API client reuse extended with retry-with-backoff for read operations (repo list, tree, file content, languages) — one retry on a transient 5xx/network error before giving up. Deliberately not applied to writes, which could risk double-executing a mutation.
- **New:** health check pings (Postgres/Redis) now cache for 5s to avoid redundant DB round-trips if Railway polls frequently.

**Stability:**
- **New:** process-level crash handlers — an uncaught exception now triggers the same clean shutdown (closing DB connections properly) instead of the process just disappearing; unhandled promise rejections are logged clearly instead of vanishing silently.
- **New:** double-tap protection on every destructive action (delete repo, delete file, bulk actions, disconnect) — a duplicate tap while the first is still processing gets a clean "already processing" reply instead of running twice.
- **New:** zip bomb guard — checks total *uncompressed* size from zip metadata before extracting a single byte, not just the compressed size we already capped.
- **Fixed:** single-file uploads (not zips) had no size cap at all — now capped at 5MB.
- **New:** timeout on the Telegram file-download fetch — a hung request no longer hangs indefinitely.
- **New:** global Express error handler — an unexpected error in a route now fails clean instead of behaving unpredictably.
- **New:** GitHub rate-limit errors now get their own specific message showing the actual reset time, instead of a generic error.
- **New:** Telegram's flood-control responses (429 + `retry_after`) are now honored during Bulk Actions' progress updates instead of just being swallowed.
- **New:** Redis reconnection events are now logged, instead of silently retrying with library defaults.
- **New:** structured logging (`lib/logger.js`) replacing scattered `console.log` across the app's core infrastructure — timestamped, leveled, consistent.
- **Improved:** Node's heap cap is now set via `NODE_OPTIONS` (an env var) instead of hardcoded in `package.json` — tunable per-plan without a redeploy.

### v0.5.0 — Fixed the OOM crash loop
Railway confirmed the bot was hitting the free tier's 512MB ceiling and getting hard-killed — happening even at rest, and faster under active use. Root-caused and fixed in layers:

- **Fixed:** Node's heap wasn't capped, so V8 never felt pressure to garbage-collect before the container's real limit — added `--max-old-space-size=384`.
- **Fixed:** Postgres pool was uncapped (up to 10 idle connections); capped to 3 via `PG_POOL_MAX`.
- **Fixed:** a new Octokit client was constructed on *every single* GitHub API call instead of being reused — now cached per token.
- **New:** graceful shutdown on `SIGTERM`/`SIGINT` — Postgres pool and Redis connection now close cleanly instead of the process just disappearing.
- **New:** a self-imposed memory watchdog that triggers a clean restart before Railway's kernel would otherwise force-kill the process.
- **Fixed (the big one):** Upload's raw file bytes were being serialized into Redis on every wizard step (path selection → summary → commit) instead of once. Now held in a short-lived in-process cache; only a lightweight reference touches session state. This directly explains "crashes faster when actively using it."
- **New:** `GET /health` endpoint for Railway to poll.
- **Cleanup:** removed `archiver` from dependencies — listed in `package.json` but never actually used anywhere in the code. Lazy-loaded `adm-zip` so it's only pulled into memory when a zip upload actually happens, not on every scene load.

### v0.4.0 — Completed the 3 noted gaps, plus another bug-scan pass
The 3 items explicitly noted as "reported, not fixed" in v0.3.1, now actually wired:

- **Notification toggles now do something** for 3 of the 4 categories:
  - ⚠️ **System Alerts** — Settings now proactively pushes a message (not just an Activity Log entry) when Postgres or Redis is unreachable, debounced to once per 10 minutes so it doesn't spam on repeated views.
  - 🔑 **Token Health** — a new shared error helper detects GitHub auth failures (expired/revoked token) anywhere in the bot and responds with the specific "reconnect" message we originally designed, instead of a generic error. Wired into Upload, Create/Rename/Delete Repo, Visibility toggle, Download, Edit File, and Bulk Actions.
  - ⏳ **Long Operations** — Bulk Actions (5+ repos) now sends an explicit "long operation finished" callout when this is on, in addition to the normal summary.
  - 🔔 **GitHub Activity** remains honestly documented as pending — it needs a receiving webhook endpoint, still a deferred item, not silently pretending to work.
- **Browse Files now paginates** (8 items/page) — a large folder no longer risks exceeding Telegram's inline-keyboard button limit.
- **Bulk Actions now stop cleanly on a bad token mid-batch** instead of grinding through every remaining repo and reporting the same failure N times — detects it once, reports it once, shows what did complete beforehand.

**Additional bugs found during this pass and fixed:**
- Deep-audited every button's callback data against the router again (habit now) — no new orphaned callbacks found this round.
- Verified the System Alert debounce logic wasn't accidentally checking its own just-written log entry (would have suppressed the very first alert every time) — caught and reordered before shipping.

### v0.3.1 — Deep audit bug fixes
A full cross-reference pass (every button's callback data checked against the router, every BBTB label checked against its handler) turned up 5 real issues, all fixed:

- **Fixed (serious):** the global ❌ Cancel button only cleared 2 of 5 possible pending session flows. Tapping Cancel while creating a tag, editing a default, or mid-way through typing "RESET" to confirm a full data wipe left that flag stuck active — meaning an unrelated later message could get silently misinterpreted in that stale context (worst case: an unrelated message happening to read "RESET" could trigger an unintended full data wipe). Cancel now clears every pending flow's flag, every time.
- **Fixed:** Edit File's and Rename Repo's confirm steps treated *any* stray callback (not just the intended button) as if it meant "confirm" — including a tap on an unrelated old button elsewhere in the chat. Both now explicitly check for the exact expected callback and reject anything else.
- **Fixed:** stale/expired button taps left Telegram's loading spinner stuck with no response. Every unmatched callback now gets an explicit "This button has expired" reply.
- **Removed:** dead code — a leftover "Upload Here" button path from before that feature was redesigned as a BBTB button; the flag that would have triggered it was never actually set anywhere.
- **Verified, not changed:** re-audited Bulk Actions' progress-line rendering (looked suspicious, traced through by hand — confirmed correct), and cross-checked every new v0.3.0 table's SQL constraints against every `ON CONFLICT` clause in the corresponding JS (all match).

**Confirmed still open** (reported, not yet fixed — awaiting direction): 3 of the 4 Notification toggles (System Alerts, Long Operations, Token Health) save state but nothing reads them yet; Browse Files has no pagination for large folders; token-expiry-mid-action doesn't route to the specific reconnect message we designed for it.

### v0.3.0 — Feature expansion
Nine new features, one long-standing bug fixed properly, added carefully so nothing sits half-wired:

- **Fixed:** Edit File's ❌ Cancel (and every exit path — success, error, stale-file conflict) dumped you at Main Menu instead of back to the exact Browse Files folder you came from.
- **Fixed:** Repo View still showed the old single-language emoji-circle format instead of the percentage breakdown already fixed elsewhere in v0.2.0 — now consistent everywhere, using the locked tree-character formatting standard.
- **New:** 📌 Pinned Repos, with manual reorder (⬆️⬇️) — entry point lives in My Repos' BBTB, not Main Menu.
- **New:** 🏷️ Tags — create/assign/remove per repo, filter My Repos by tag, bulk-select by tag, shown as chips wherever a repo is listed.
- **New:** 🧹 Bulk Repo Actions — multi-select with smart shortcuts (Select All, Invert, Stale 6mo+, by visibility, by tag), delete/visibility/download in one pass, live per-item progress, and an honest partial-failure report if some fail.
- **New:** 📥 Batch Upload — the existing Upload flow now collects multiple loose files before asking for a path, one combined commit.
- **New:** 🔁 Replace (file) and 🔁 Replace Folder (full sync with an explicit delete-preview before committing — the only place Upload is allowed to remove files, and only with your confirmation).
- **New:** ⬆️ Upload Here — uploads straight into whatever folder you're browsing.
- **New:** ⚙️ My Defaults — saved visibility/commit-message/upload-path/sort/filter, with a pattern-based "learn from me" suggestion after 3 consistent choices.
- **New:** 📦 Storage & Data — live counts of what GitroHub stores about you, granular or full-reset clearing (full reset requires typing "RESET", not just a tap), JSON/text export, and configurable auto-cleanup.
- **New:** 🔑 Access Log — separate from general Activity, tracks connect/reconnect/disconnect events specifically, with an optional alert on new connections.
- **Internal:** caught and fixed two features that were built but never wired to anything callable (`checkVisibilityPattern`, `getLastPath`) during a dead-code sweep before release — both now genuinely affect the Create Repo and Upload flows.
- **Internal:** caught and fixed two new `reply_markup` BBTB/inline conflicts (same class of bug as v0.1.1) introduced in the new Bulk Select screens, caught by the same automated scan before shipping.

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
TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 24)
NODE_OPTIONS=--max-old-space-size=384
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

## ⚠️ Known limitations in this v0.4.0 build

Being upfront about what's simplified, consistent with the "specific errors, not vague ones" principle applied to the docs too:

- **"Browse Folders" during single-file upload path selection** still falls back to type-path (with the repo's current structure shown for context, a one-tap Root shortcut, and remembered-path suggestions) — the folder-tap navigator for *choosing* an upload destination wasn't wired up. Browsing an *existing* tree (Browse Files) is fully implemented, including pagination.
- **GitHub webhook-based notifications** (stars/issues/PRs) are schema-ready and the toggle exists in Settings, but the receiving webhook endpoint isn't implemented yet — still a deferred item, and the only Notification category that doesn't yet do anything (the other 3 do, as of v0.4.0).
- **🟢🟡🔴 Activity Status indicator** and **🍴 "Forked from X" tag** were explicitly deferred to a future version during design.
- **Text/slash-command fallback** for repo actions (e.g. `/repos`) isn't implemented — `/start`, `/settings`, `/cancel` exist as commands, but the button-driven UI remains the primary interface for everything else.
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
