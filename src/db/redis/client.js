'use strict';

const Redis = require('ioredis');
const env = require('../../config/env');
const logger = require('../../utils/logger');

const redis = new Redis(env.REDIS_URL, {
  maxRetriesPerRequest: 3,
  connectTimeout: 5000,
  lazyConnect: false,
});

redis.on('error', (err) => logger.error({ err }, 'Redis connection error'));
redis.on('connect', () => logger.info('✅ Redis connected'));

async function ping() {
  const start = Date.now();
  await redis.ping();
  return Date.now() - start;
}

module.exports = { redis, ping };
