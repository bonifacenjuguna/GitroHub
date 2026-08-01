'use strict';

const { redis } = require('./client');

const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days of inactivity before a session is dropped
const PREFIX = 'gitrohub:session:';

/**
 * grammY-compatible StorageAdapter backed by Redis.
 * Keeps session objects small — only ephemeral navigation/flow state lives
 * here (activeRepoId, pendingAction, uploadState, etc.), never large blobs
 * like full file contents.
 */
const redisSessionStorage = {
  async read(key) {
    const raw = await redis.get(PREFIX + key);
    return raw ? JSON.parse(raw) : undefined;
  },
  async write(key, value) {
    await redis.set(PREFIX + key, JSON.stringify(value), 'EX', SESSION_TTL_SECONDS);
  },
  async delete(key) {
    await redis.del(PREFIX + key);
  },
};

module.exports = redisSessionStorage;
