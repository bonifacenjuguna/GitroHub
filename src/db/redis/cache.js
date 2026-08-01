'use strict';

const { redis } = require('./client');

/** Wraps an async fetcher with a Redis cache. Returns cached value if present. */
async function cached(key, ttlSeconds, fetcher) {
  const hit = await redis.get(key);
  if (hit) return JSON.parse(hit);

  const fresh = await fetcher();
  await redis.set(key, JSON.stringify(fresh), 'EX', ttlSeconds);
  return fresh;
}

async function invalidate(keyOrPattern) {
  if (keyOrPattern.includes('*')) {
    const keys = await redis.keys(keyOrPattern);
    if (keys.length) await redis.del(...keys);
  } else {
    await redis.del(keyOrPattern);
  }
}

/** Stores the last-known GitHub rate limit snapshot for fast display without an extra API call. */
async function setRateLimitSnapshot(telegramUserId, snapshot) {
  await redis.set(`gitrohub:ratelimit:${telegramUserId}`, JSON.stringify(snapshot), 'EX', 300);
}

async function getRateLimitSnapshot(telegramUserId) {
  const raw = await redis.get(`gitrohub:ratelimit:${telegramUserId}`);
  return raw ? JSON.parse(raw) : null;
}

/** Simple in-flight guard to prevent duplicate handling of rapid double-taps on the same button. */
async function guardInFlight(telegramUserId, callbackData, ttlMs = 2000) {
  const key = `gitrohub:inflight:${telegramUserId}:${callbackData}`;
  const set = await redis.set(key, '1', 'PX', ttlMs, 'NX');
  return set === 'OK'; // true = safe to proceed, false = duplicate tap, ignore
}

module.exports = { cached, invalidate, setRateLimitSnapshot, getRateLimitSnapshot, guardInFlight };
