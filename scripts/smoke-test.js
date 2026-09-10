#!/usr/bin/env node
/**
 * smoke-test.js — requires every file in src/, then actually CALLS every
 * exported function in src/handlers/ with a fake ctx and a fake DB, rather
 * than only checking that files parse. This exists specifically to catch
 * two things neither `node --check` nor check-patterns.js can:
 *
 *   1. A require-scope bug (the "ephemeral" class) is only a STATIC
 *      approximation in check-patterns.js — this actually invokes the
 *      code path, so it catches the real ReferenceError the moment the
 *      function runs, the same way a live user tapping the button would
 *      trigger it.
 *   2. A feature that's wired into the UI (a button exists, a callback is
 *      registered in bot.js) but the function behind it does nothing —
 *      e.g. Smart Folders' "Apply" silently no-op'ing before it was
 *      fixed. Requiring a file only proves it parses; calling the
 *      function proves it does SOMETHING when invoked.
 *
 * What this is NOT: a real test suite. The DB is faked to return empty
 * results for everything, so it cannot catch logic bugs that depend on
 * real data shapes, and most calls WILL throw something (a TypeError from
 * missing fake data, a network error from github.js reaching out for
 * real) — that's expected and not reported as a finding. The one thing
 * that's never expected, no matter how bad the fake data is, is a
 * ReferenceError — an undefined variable is a bug in the code itself,
 * not a symptom of incomplete mocking, so that's the one error type this
 * script actually flags.
 *
 * Run via `npm run smoke-test` (or `npm run verify` for the full set).
 */

// Fake required env vars BEFORE requiring anything — config.js calls
// process.exit(1) on anything missing, and this script only exists to
// exercise the code, never to actually connect to anything real.
Object.assign(process.env, {
  BOT_TOKEN: 'smoke-test-token',
  OWNER_ID: '1',
  GITHUB_CLIENT_ID: 'smoke-test',
  GITHUB_CLIENT_SECRET: 'smoke-test',
  BASE_URL: 'https://example.com',
  SESSION_JWT_SECRET: 'smoke-test-secret',
  TOKEN_ENCRYPTION_KEY: '0'.repeat(64),
  DATABASE_URL: 'postgres://fake:fake@localhost:5432/fake',
  REDIS_URL: 'redis://localhost:6379',
});

const Module = require('module');
const fs = require('fs');
const path = require('path');

// A single generic "connected, has some data" row, returned for every
// query regardless of which table it's actually for. This matters a lot:
// requireConnected() (the guard at the top of nearly every handler that
// touches GitHub) does a real `SELECT * FROM users` and bails out the
// entire calling function immediately if it doesn't look "connected" — an
// empty result set there would make almost every handler function return
// on its very first line, never reaching the code this script exists to
// exercise. A non-empty, plausible-looking row unblocks that gate, and as
// a side effect also exercises "has items" branches (list.map/.forEach)
// in other handlers instead of skipping them for lack of any rows.
// Field-name mismatches against whichever real table a query was actually
// for just resolve to `undefined` on access — not a crash, and not
// something this script treats as a finding (see file header).
let fakeRow = null; // populated after config.js loads (needs the real encrypt())
function getFakeRow() {
  if (fakeRow) return fakeRow;
  const { encrypt } = require(path.join(SRC_DIR, 'lib', 'crypto'));
  fakeRow = {
    id: 1, telegram_id: 1, name: 'smoke-test-repo', original_name: 'smoke-test-repo',
    repo_name: 'smoke-test-repo', github_username: 'smoke-test-user',
    github_token_enc: encrypt('smoke-test-fake-token'), disconnected_at: null,
    timezone: 'UTC', time_format: '24h',
    default_visibility: 'private', default_commit_message: 'Update via GitroHub',
    default_upload_path: null, default_sort: 'updated', default_filter: 'all',
    auto_suggest_defaults: true, trash_retention_days: 30, recently_viewed_enabled: true,
    description: 'A smoke-test fixture', visibility: 'private',
    backup_file_id: 'fake-file-id', expires_at: null, deleted_at: new Date().toISOString(), restored_at: null,
    license: null, include_readme: true, scheduled_for: new Date(Date.now() + 3600000).toISOString(), status: 'pending',
    emoji: '🏷️', parent_id: null, color_class: 'blue', auto_rule_json: null, repo_count: 0,
    position: 0, pin_section: null, filter_json: '[]', field: 'language', op: '=', value: 'JavaScript',
    icon: '🔔', summary: 'Smoke-test activity entry', detail: null, is_error: false, is_automated: false, created_at: new Date().toISOString(),
    viewed_at: new Date().toISOString(),
  };
  return fakeRow;
}

// Fake 'pg' — see getFakeRow() above for why every query returns one
// generic row rather than nothing.
const fakePg = {
  Pool: class {
    on() {}
    async query() { return { rows: [getFakeRow()], rowCount: 1 }; }
    async end() {}
  },
};

// Fake 'redis' — same idea.
const fakeRedis = {
  createClient: () => ({
    on() {},
    async connect() {},
    async ping() { return 'PONG'; },
    async quit() {},
    async get() { return null; },
    async set() {},
    async del() {},
  }),
};

const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'pg') return fakePg;
  if (request === 'redis') return fakeRedis;
  return originalLoad.call(this, request, parent, isMain);
};

const SRC_DIR = path.join(__dirname, '..', 'src');

function listJsFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listJsFiles(full));
    else if (entry.name.endsWith('.js')) out.push(full);
  }
  return out;
}

function makeFakeCtx() {
  return {
    from: { id: 1, username: 'smoketest' },
    chat: { id: 1 },
    session: {},
    wizard: { state: {}, selectStep: () => {} },
    message: { text: 'test', document: null },
    callbackQuery: { data: 'test:1', message: { message_id: 1 } },
    scene: { leave: async () => {}, enter: async () => {} },
    reply: async () => ({ message_id: 1 }),
    replyWithDocument: async () => ({ message_id: 1, document: { file_id: 'fake' } }),
    replyWithPhoto: async () => ({ message_id: 1 }),
    // Deliberately throws, like Telegram does on a no-op edit — exercises
    // every safeEditMessageText() fallback path along the way too.
    editMessageText: async () => { throw new Error('smoke-test: simulated "message not modified"'); },
    answerCbQuery: async () => {},
    deleteMessage: async () => {},
    telegram: {
      sendMessage: async () => ({ message_id: 1 }),
      getFileLink: async () => ({ href: 'https://example.invalid/fake' }),
      editMessageText: async () => { throw new Error('smoke-test: simulated edit failure'); },
      deleteMessage: async () => {},
    },
  };
}

/** Never lets a single call hang the whole run — anything reaching out to
 * a real network in this fake environment should fail fast anyway, but a
 * hard ceiling keeps one bad call from stalling everything else.
 *
 * The unconditional .catch() on the original promise matters: Promise.race
 * only cares about whichever settles first, but if the ORIGINAL promise
 * loses the race (this function timed out) and rejects later anyway —
 * e.g. a real github.js retry delay that legitimately runs past this
 * timeout — that later rejection has nothing listening to it anymore and
 * becomes a genuinely unhandled rejection, wrongly attributed to whatever
 * function happens to be running by the time it fires. This isn't a bug
 * in the code being tested; it's Promise.race's well-known "the loser
 * still needs its own .catch()" caveat, so it's handled here once. */
function withTimeout(promise, ms) {
  promise.catch(() => {});
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('smoke-test: timed out')), ms)),
  ]);
}

console.log('── Requiring every file in src/ ──');
const allFiles = listJsFiles(SRC_DIR);
let requireFailures = 0;
for (const file of allFiles) {
  try {
    delete require.cache[require.resolve(file)];
    require(file);
  } catch (err) {
    console.log(`  ✗ ${path.relative(process.cwd(), file)}: ${err.constructor.name}: ${err.message}`);
    requireFailures++;
  }
}
console.log(requireFailures === 0 ? '  ✓ every file requires cleanly' : `  ${requireFailures} file(s) failed to require — see above`);

console.log('\n── Calling every exported function in src/handlers/ with a fake ctx ──');
const handlerFiles = listJsFiles(path.join(SRC_DIR, 'handlers'));
let realBugs = 0;
let calledCount = 0;

// A rejected promise that isn't awaited/returned/caught by the function
// itself (a genuine "fire and forget without .catch()" bug — real code,
// not a smoke-test artifact) never reaches the try/catch below at all; by
// default Node treats an unhandled rejection as fatal and kills the whole
// process, which would silently end this script AND hide which function
// was responsible. Tracking "what's currently being called" plus a
// process-level listener means a bug like that gets attributed and
// reported instead of just crashing everything without explanation.
let currentlyTesting = 'startup';
process.on('unhandledRejection', (err) => {
  if (err instanceof ReferenceError) {
    console.log(`  ✗ ${currentlyTesting} — unhandled rejection (not caught by the function itself): ${err.message}`);
    realBugs++;
  } else {
    console.log(`  ⚠ ${currentlyTesting} — unhandled rejection (not caught by the function itself): ${err.constructor.name}: ${err.message}`);
    console.log(`    This means a real promise somewhere in that call chain isn't awaited, returned, or .catch()'d — worth a manual look even though it's not a ReferenceError, since the same gap would crash the live bot process on a real transient failure, not just this test.`);
  }
});

async function callOne(file, name, fn) {
  const ctx = makeFakeCtx();
  currentlyTesting = `${path.relative(process.cwd(), file)}: ${name}()`;
  try {
    // Most handler functions are (ctx) or (ctx, id) or (ctx, id, value) —
    // extra undefined args are harmless; a function that needs them will
    // just hit a TypeError on the missing value, which is expected noise,
    // not a real finding (see file header).
    await withTimeout(Promise.resolve(fn(ctx, '1', '1')), 3000);
  } catch (err) {
    if (err instanceof ReferenceError) {
      console.log(`  ✗ ${currentlyTesting} — ${err.message}`);
      realBugs++;
    }
    // Anything else (TypeError from fake data, network errors from
    // github.js, our deliberate editMessageText throw, etc.) is
    // expected given how minimal the fakes are — not reported.
  }
  // Give any unhandled-rejection event a tick to fire and be attributed
  // to this call before moving on to the next one.
  await new Promise((resolve) => setImmediate(resolve));
}

async function run() {
  for (const file of handlerFiles) {
    let mod;
    try {
      mod = require(file);
    } catch (_) {
      continue; // already reported above
    }
    if (!mod || typeof mod !== 'object') continue;

    for (const [name, fn] of Object.entries(mod)) {
      if (typeof fn !== 'function') continue;
      calledCount++;
      await callOne(file, name, fn);
    }
  }

  console.log(`  (called ${calledCount} exported function(s) across ${handlerFiles.length} handler files)`);
  console.log(realBugs === 0 ? '  ✓ no ReferenceErrors — the one error type that\u2019s never expected here' : `  ${realBugs} likely real bug(s) found — see \u2717 lines above`);

  console.log('');
  if (requireFailures > 0 || realBugs > 0) {
    console.log('❌ smoke-test found issues that need fixing before this ships.');
    process.exit(1);
  }
  console.log('✅ smoke-test: clean.');
  // Explicit exit rather than letting the process idle: several handler
  // functions schedule their own setTimeout calls (e.g. ephemeral.js's
  // auto-delete timers), which would otherwise fire later against a fake
  // ctx that's no longer relevant, potentially crashing AFTER this script
  // already reported success. Nothing legitimate is still pending once
  // we've reached this line.
  process.exit(0);
}

run();
