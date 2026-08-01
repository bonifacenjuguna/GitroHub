'use strict';

const crypto = require('crypto');
const env = require('../config/env');

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12; // 96-bit IV, recommended for GCM
const AUTH_TAG_LENGTH = 16;
const SALT_LENGTH = 16;

/**
 * Derives a unique 256-bit key per user from the master key + a per-user
 * salt, using scrypt. This means even if one derived key were ever
 * compromised, other users' tokens (in a future multi-tenant scenario)
 * would remain safe — and it means the master key itself is never used
 * directly to encrypt data.
 */
function deriveKey(salt) {
  return crypto.scryptSync(env.ENCRYPTION_MASTER_KEY, salt, 32);
}

/**
 * Encrypts a plaintext string (e.g. a GitHub OAuth token).
 * Returns a single base64 string containing salt + iv + authTag + ciphertext,
 * safe to store directly in a single Postgres column.
 */
function encrypt(plaintext) {
  const salt = crypto.randomBytes(SALT_LENGTH);
  const key = deriveKey(salt);
  const iv = crypto.randomBytes(IV_LENGTH);

  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(String(plaintext), 'utf8'), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return Buffer.concat([salt, iv, authTag, encrypted]).toString('base64');
}

/**
 * Decrypts a string previously produced by encrypt().
 * Throws if the payload has been tampered with (GCM auth tag mismatch).
 */
function decrypt(payload) {
  const buffer = Buffer.from(payload, 'base64');

  const salt = buffer.subarray(0, SALT_LENGTH);
  const iv = buffer.subarray(SALT_LENGTH, SALT_LENGTH + IV_LENGTH);
  const authTag = buffer.subarray(SALT_LENGTH + IV_LENGTH, SALT_LENGTH + IV_LENGTH + AUTH_TAG_LENGTH);
  const ciphertext = buffer.subarray(SALT_LENGTH + IV_LENGTH + AUTH_TAG_LENGTH);

  const key = deriveKey(salt);
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);

  const decrypted = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  return decrypted.toString('utf8');
}

/** Generates a cryptographically secure random state token for OAuth CSRF protection. */
function generateStateToken() {
  return crypto.randomBytes(32).toString('hex');
}

/** Generates a short numeric-safe hash reference for error logs (never exposes internals). */
function generateErrorRef() {
  return 'ERR-' + crypto.randomBytes(4).toString('hex');
}

module.exports = { encrypt, decrypt, generateStateToken, generateErrorRef };
