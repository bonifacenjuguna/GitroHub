# Privacy Policy

**Last updated: July 31, 2026**

## What We Collect

- **Telegram identity** — your numeric user ID, username, and first/last
  name, used to identify your session and personalize responses.
- **GitHub OAuth token** — encrypted at rest with AES-256-GCM, used solely
  to make GitHub API requests on your behalf.
- **Action logs** — a record of sensitive actions (repository deletion,
  visibility changes, merges, disconnects) kept for your own Activity Log
  and for abuse-prevention diagnostics.
- **Preferences** — display settings, default repo behavior, notification
  preferences, pinned repos, and custom command shortcuts.

## What We Do NOT Collect

- Your GitHub password — GitroHub uses OAuth exclusively and never sees it.
- Permanent copies of your source code — uploaded files are processed and
  committed immediately, then discarded; nothing is retained beyond the
  commit itself.
- Any data sold or shared with third parties for advertising or any other
  purpose — this never happens.

## How Data Is Secured

- GitHub tokens are encrypted with AES-256-GCM using a key uniquely
  derived per account via scrypt.
- Secrets sent in chat (e.g. repository secret values) are deleted from
  the chat history immediately after being read by the bot.
- All destructive actions require explicit in-chat confirmation.

## Data Retention

- Preferences and activity logs are retained until you delete your
  GitroHub account (via Settings → Account → Delete My GitroHub Account),
  at which point all associated data is permanently erased.
- Redis-backed session/cache data is ephemeral by design and expires
  automatically.

## Your Rights

You may delete your GitroHub account and all associated data at any time
directly within the bot. For questions about data handling not covered
here, contact the copyright holder directly.

## Third-Party Services

GitroHub's operation depends on the GitHub API, the Telegram Bot API, and
Railway (hosting, PostgreSQL, Redis). Each processes data under its own
respective privacy policy.
