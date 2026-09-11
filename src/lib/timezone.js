/**
 * Timezone conversion using only Node's built-in `Intl` — no date library
 * dependency (no network access in the dev environment to install/verify
 * one). Node's Intl can *format* a Date in any IANA zone out of the box,
 * but can't *parse* "this local time in that zone" back to UTC on its own,
 * so zonedTimeToUtc() does that with a standard guess-and-correct pass:
 * render a candidate UTC instant in the target zone, measure how far off
 * it is from the intended local time, and correct by that difference.
 * Verified against known UTC offsets including DST transitions (Europe/
 * London BST vs GMT) before this was relied on for anything.
 */

const COMMON_ZONES = [
  { id: 'UTC', label: 'UTC' },
  { id: 'America/New_York', label: 'New York' },
  { id: 'America/Chicago', label: 'Chicago' },
  { id: 'America/Denver', label: 'Denver' },
  { id: 'America/Los_Angeles', label: 'Los Angeles' },
  { id: 'America/Sao_Paulo', label: 'São Paulo' },
  { id: 'Europe/London', label: 'London' },
  { id: 'Europe/Berlin', label: 'Berlin' },
  { id: 'Europe/Moscow', label: 'Moscow' },
  { id: 'Africa/Lagos', label: 'Lagos' },
  { id: 'Africa/Nairobi', label: 'Nairobi' },
  { id: 'Africa/Cairo', label: 'Cairo' },
  { id: 'Asia/Dubai', label: 'Dubai' },
  { id: 'Asia/Kolkata', label: 'Mumbai/Delhi' },
  { id: 'Asia/Shanghai', label: 'Shanghai' },
  { id: 'Asia/Tokyo', label: 'Tokyo' },
  { id: 'Australia/Sydney', label: 'Sydney' },
];

/** Converts a "YYYY-MM-DD" + "HH:MM" pair, understood as local time in
 * `timeZone`, into the correct UTC Date. Two correction passes handle the
 * (rare) case where the first correction crosses a DST boundary itself. */
function zonedTimeToUtc(dateStr, timeStr, timeZone) {
  const [y, mo, d] = dateStr.split('-').map(Number);
  const [h, mi] = timeStr.split(':').map(Number);
  let guess = new Date(Date.UTC(y, mo - 1, d, h, mi));

  for (let i = 0; i < 2; i++) {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
    const parts = Object.fromEntries(fmt.formatToParts(guess).map((p) => [p.type, p.value]));
    const renderedAsUTC = Date.UTC(+parts.year, +parts.month - 1, +parts.day, parts.hour === '24' ? 0 : +parts.hour, +parts.minute);
    const intendedAsUTC = Date.UTC(y, mo - 1, d, h, mi);
    guess = new Date(guess.getTime() + (intendedAsUTC - renderedAsUTC));
  }
  return guess;
}

/** Formats a UTC Date as local date+time text in the given zone.
 * hour12 is purely cosmetic (My Defaults → 🌍 Timezone) — every stored
 * time is still UTC internally either way. */
function formatInZone(date, timeZone, { withDate = true, hour12 = false } = {}) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone,
    ...(withDate ? { dateStyle: 'medium' } : {}),
    timeStyle: 'short',
    hour12,
  }).format(date);
}

/** Validates an IANA zone name the cheap way — ask Intl to use it and see
 * if it throws, rather than shipping our own list of every valid zone. */
function isValidTimeZone(tz) {
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: tz });
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Per-zone clock/calendar reads, used anywhere a background job needs to
 * know "is it currently the right local moment for THIS person" instead
 * of comparing against a single shared UTC instant — see index.js's
 * quiet-hours check, Rollup scheduler, and weekly automation, none of
 * which should fire at the same instant for every user regardless of
 * where they actually are.
 */

/** 0–23 hour of the day, in the given zone, for the given instant. */
function getHourInZone(date, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', hourCycle: 'h23' }).formatToParts(date);
  return Number(parts.find((p) => p.type === 'hour').value);
}

/** 0 (Sunday) – 6 (Saturday) day of the week, in the given zone. Needed
 * because "is it Monday" depends on which zone you're asking from — the
 * UTC date can already be a different weekday than someone's local one,
 * especially close to midnight in either direction. */
const WEEKDAY_INDEX = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
function getWeekdayInZone(date, timeZone) {
  const weekday = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'short' }).format(date);
  return WEEKDAY_INDEX[weekday];
}

/** YYYY-MM-DD calendar date, in the given zone — for "once per local day"
 * dedup markers, so the day boundary a scheduler uses to decide "have I
 * already sent this today" matches the day the person actually
 * experiences, not whatever day it happens to be in UTC when they're
 * close to their own local midnight. */
function getDateKeyInZone(date, timeZone) {
  return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
}

/**
 * Accepts a few date/time shapes for "when should this happen", all
 * understood as local time in `timeZone`, and returns the equivalent UTC
 * Date — or null if none of them match. Full "YYYY-MM-DD HH:MM" always
 * works, but typing the year and month every time is needless friction
 * for "later today" or "next Tuesday" style scheduling, so shorter forms
 * fill in whatever's missing from the current date in that zone:
 *
 *   "HH:MM"             — today, or tomorrow if that time already passed
 *   "MM-DD HH:MM"        — this year, or next year if that date already passed
 *   "YYYY-MM-DD HH:MM"   — exactly as given
 *
 * The hour can be 24h ("14:30") or 12h with am/pm ("2:30pm", "2:30 PM"),
 * regardless of the person's own 24h/12h display preference — that
 * preference only affects how times are *shown*, not what's accepted here.
 */
function parseFlexibleDateTime(input, timeZone) {
  const cleaned = input.trim().toLowerCase();
  const timeMatch = cleaned.match(/(\d{1,2}):(\d{2})\s*(am|pm)?$/);
  if (!timeMatch) return null;

  let hour = Number(timeMatch[1]);
  const minute = Number(timeMatch[2]);
  const meridiem = timeMatch[3];
  if (minute > 59) return null;
  if (meridiem) {
    if (hour < 1 || hour > 12) return null;
    if (meridiem === 'pm' && hour !== 12) hour += 12;
    if (meridiem === 'am' && hour === 12) hour = 0;
  } else if (hour > 23) {
    return null;
  }
  const timeStr = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
  const datePart = cleaned.slice(0, timeMatch.index).trim();

  const nowLocalStr = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const [nowY, nowM, nowD] = nowLocalStr.split('-').map(Number);
  const pad = (n) => String(n).padStart(2, '0');

  if (datePart === '') {
    let y = nowY, mo = nowM, d = nowD;
    let candidate = zonedTimeToUtc(`${y}-${pad(mo)}-${pad(d)}`, timeStr, timeZone);
    if (candidate.getTime() <= Date.now()) {
      const tomorrow = new Date(Date.UTC(y, mo - 1, d + 1));
      candidate = zonedTimeToUtc(`${tomorrow.getUTCFullYear()}-${pad(tomorrow.getUTCMonth() + 1)}-${pad(tomorrow.getUTCDate())}`, timeStr, timeZone);
    }
    return candidate;
  }

  const fullMatch = datePart.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (fullMatch) {
    const [, y, mo, d] = fullMatch;
    return zonedTimeToUtc(`${y}-${pad(Number(mo))}-${pad(Number(d))}`, timeStr, timeZone);
  }

  const shortMatch = datePart.match(/^(\d{1,2})-(\d{1,2})$/);
  if (shortMatch) {
    const mo = Number(shortMatch[1]);
    const d = Number(shortMatch[2]);
    let candidate = zonedTimeToUtc(`${nowY}-${pad(mo)}-${pad(d)}`, timeStr, timeZone);
    if (candidate.getTime() <= Date.now()) {
      candidate = zonedTimeToUtc(`${nowY + 1}-${pad(mo)}-${pad(d)}`, timeStr, timeZone);
    }
    return candidate;
  }

  return null;
}

module.exports = {
  COMMON_ZONES, zonedTimeToUtc, formatInZone, isValidTimeZone, parseFlexibleDateTime,
  getHourInZone, getWeekdayInZone, getDateKeyInZone,
};
