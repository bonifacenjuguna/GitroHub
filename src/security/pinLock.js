'use strict';

const crypto = require('crypto');

/** Hashes a 4-digit PIN with a random salt using scrypt (never store PINs in plaintext). */
function hashPin(pin) {
  const salt = crypto.randomBytes(16);
  const hash = crypto.scryptSync(pin, salt, 32);
  return `${salt.toString('hex')}:${hash.toString('hex')}`;
}

function verifyPin(pin, storedHash) {
  if (!storedHash) return false;
  const [saltHex, hashHex] = storedHash.split(':');
  const salt = Buffer.from(saltHex, 'hex');
  const expected = Buffer.from(hashHex, 'hex');
  const actual = crypto.scryptSync(pin, salt, 32);
  return crypto.timingSafeEqual(expected, actual);
}

const PIN_REQUIRED_ACTIONS = new Set([
  'delete_repo', 'change_visibility', 'disconnect_github', 'force_push', 'delete_release',
]);

function actionRequiresPin(actionType) {
  return PIN_REQUIRED_ACTIONS.has(actionType);
}

module.exports = { hashPin, verifyPin, actionRequiresPin };
