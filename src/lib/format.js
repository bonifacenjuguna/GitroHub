/**
 * Central formatting helpers — implements the standing "Formatting Standard"
 * rule agreed on during design: consistent headers, key-value lines, relative
 * timestamps, language-color emoji, and the locked error/success message shapes.
 *
 * Keeping ALL formatting logic here means every screen in the bot renders
 * consistently, and if the style ever changes we only edit one file.
 */

// GitHub's real language colors, approximated with the closest emoji circle.
const LANGUAGE_EMOJI = {
  JavaScript: '🟨',
  TypeScript: '🔵',
  Python: '🔵',
  HTML: '🟧',
  CSS: '🟪',
  Shell: '🟩',
  Java: '🟫',
  Go: '🔷',
  Rust: '🟠',
  C: '⬜',
  'C++': '🩷',
  'C#': '🟢',
  PHP: '🟣',
  Ruby: '🔴',
  Swift: '🟠',
  Kotlin: '🟣',
  Dart: '🔵',
};

function languageEmoji(lang) {
  if (!lang) return '⚪';
  return LANGUAGE_EMOJI[lang] || '⚪';
}

function languageLine(lang) {
  return lang ? `${languageEmoji(lang)} ${lang}` : '⚪ No language detected';
}

/**
 * Turns { JavaScript: 12000, HTML: 4000 } into "JavaScript 75% · HTML 25%".
 * `limit` caps how many languages are shown (default 3, for compact repo-card
 * use in lists); pass `null`/`Infinity` to list every language GitHub
 * reports — used by the full Repo View screen.
 */
function languageBreakdown(languages, limit = 3) {
  const entries = Object.entries(languages || {});
  if (entries.length === 0) return 'No language detected';
  const total = entries.reduce((sum, [, bytes]) => sum + bytes, 0);
  const cap = limit == null ? entries.length : limit;
  return entries
    .sort((a, b) => b[1] - a[1])
    .slice(0, cap)
    .map(([lang, bytes]) => `${lang} ${Math.round((bytes / total) * 100)}%`)
    .join(' · ');
}

function visibilityLine(isPrivate) {
  return isPrivate ? '🔒 Private' : '🌐 Public';
}

function licenseLine(repo) {
  return (repo && repo.license && (repo.license.spdx_id || repo.license.name)) || 'No license';
}

/**
 * The standard section header used at the top of every repo-list-style
 * screen (My Repos, Pinned, Search, Stats): "◆ TITLE ──────── N total"
 */
function sectionHeader(title, count, countLabel = 'total') {
  return `◆ ${title} ${'─'.repeat(8)} ${count} ${countLabel}`;
}

/**
 * Standard repo-card block, used everywhere a repo is listed as its own
 * message-text entry (My Repos, Repo View summary line, Pinned, Search).
 * Caller joins cards with the standard "──────────────────" divider.
 */
function repoCard(repo, { langLine, pinned = false, extraLines = [] } = {}) {
  const sizeText = formatBytes((repo.size || 0) * 1024);
  const lines = [
    `${pinned ? '📌 ' : ''}${escapeMd(repo.name)}`,
    `▸ ${escapeMd(langLine)} · ${visibilityLine(repo.private)} · ${escapeMd(sizeText)} · ${escapeMd(licenseLine(repo))}`,
    `▸ ★ ${repo.stargazers_count}  🍴 ${repo.forks_count}  ·  🕒 ${escapeMd(relativeTime(repo.updated_at))}`,
    `▸ ${repo.description ? `"${escapeMd(repo.description)}"` : 'No description yet'}`,
  ];
  for (const extra of extraLines) lines.push(`▸ ${extra}`);
  return lines.join('\n');
}

/** Relative timestamp per the locked rule: "12m ago" / "2h ago" / "3d ago" / "Month Year" */
function relativeTime(dateInput) {
  const date = new Date(dateInput);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 30) return `${diffDay}d ago`;

  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Locked error shape: "⚠️ [What failed]: [specific reason].\n[Next step]" */
function errorMessage(what, reason, nextStep) {
  let msg = `⚠️ ${what}: ${reason}.`;
  if (nextStep) msg += `\n${nextStep}`;
  return msg;
}

/** Locked success shape: "✅ [What happened].\n[optional detail]" */
function successMessage(what, detail) {
  let msg = `✅ ${what}.`;
  if (detail) msg += `\n${detail}`;
  return msg;
}

/** Escapes MarkdownV2 reserved characters for safe Telegram rendering */
function escapeMd(text = '') {
  return String(text).replace(/([_*[\]()~`>#+\-=|{}.!\\])/g, '\\$1');
}

/** Inside ``` code blocks, MarkdownV2 only requires escaping backslash and backtick */
function escapeCodeBlock(text = '') {
  return String(text).replace(/([\\`])/g, '\\$1');
}

module.exports = {
  languageEmoji,
  languageLine,
  languageBreakdown,
  visibilityLine,
  licenseLine,
  sectionHeader,
  repoCard,
  relativeTime,
  formatBytes,
  errorMessage,
  successMessage,
  escapeMd,
  escapeCodeBlock,
};
