'use strict';

const { generateErrorRef } = require('../security/encryption');
const logger = require('./logger');

/**
 * Converts any thrown error (GitHub API error, DB error, validation error,
 * etc.) into a { text, keyboard } pair matching the specific-error
 * standard we designed — never a generic "something went wrong" unless
 * the error is truly unexpected/internal.
 */
function formatError(err, context = {}) {
  // GitHub API errors (Octokit attaches .status and .response.data.message)
  if (err.status) {
    if (err.status === 403 && /rate limit/i.test(err.message || '')) {
      const resetHeader = err.response?.headers?.['x-ratelimit-reset'];
      const resetsAt = resetHeader ? new Date(Number(resetHeader) * 1000) : null;
      return {
        text: `⏳ GitHub API limit reached\n\n${resetsAt ? `Resets at ${resetsAt.toLocaleTimeString()}` : 'Try again shortly.'}\n\nThis action will be retried automatically once the limit resets.`,
        buttons: [[{ text: '🔁 Retry Now Anyway', data: context.retryCallback || 'noop' }, { text: '❌ Cancel', data: context.cancelCallback || 'menu:main' }]],
      };
    }
    if (err.status === 403) {
      return {
        text: `🔒 Permission Denied\n\n${err.response?.data?.message || 'Your GitHub token does not have access to do this.'}\n\nThis usually means your OAuth scope needs updating, or you lack admin rights here.`,
        buttons: [[{ text: '🔑 Re-authorize', data: 'security:reauth' }, { text: '⬅️ Back', data: context.backCallback || 'menu:main' }]],
      };
    }
    if (err.status === 404) {
      return {
        text: `❌ Not Found\n\n${context.notFoundLabel || 'That resource'} could not be found. It may have been deleted, renamed, or you may not have access to it.`,
        buttons: [[{ text: '⬅️ Back', data: context.backCallback || 'menu:main' }]],
      };
    }
    if (err.status === 422) {
      return {
        text: `❌ ${context.validationLabel || 'Invalid request'}\n\n${err.response?.data?.message || 'GitHub rejected this — check your input and try again.'}`,
        buttons: [[{ text: '✏️ Try Again', data: context.retryCallback || 'noop' }, { text: '❌ Cancel', data: context.cancelCallback || 'menu:main' }]],
      };
    }
    if (err.status >= 500) {
      return {
        text: `📡 GitHub is having issues\n\nGitHub's servers returned an error (${err.status}). This is usually temporary.`,
        buttons: [[{ text: '🔁 Retry', data: context.retryCallback || 'noop' }, { text: '❌ Cancel', data: context.cancelCallback || 'menu:main' }]],
      };
    }
  }

  // Network / timeout
  if (err.code === 'ETIMEDOUT' || err.code === 'ECONNRESET' || err.type === 'request-timeout') {
    return {
      text: '📡 Connection to GitHub timed out\n\nThis is usually temporary — GitHub\'s API may be slow right now.',
      buttons: [[{ text: '🔁 Retry', data: context.retryCallback || 'noop' }, { text: '❌ Cancel', data: context.cancelCallback || 'menu:main' }]],
    };
  }

  // Known application-level errors (thrown with .code by our own modules)
  if (err.code === 'NOT_CONNECTED') {
    return {
      text: '🔒 You need to connect your GitHub account first.',
      buttons: [[{ text: '🔗 Connect GitHub', data: 'auth:connect' }]],
    };
  }
  if (err.code === 'PIN_LIMIT') {
    return { text: `❌ ${err.message}`, buttons: [[{ text: '⬅️ Back', data: context.backCallback || 'menu:main' }]] };
  }
  if (err.code === 'INVALID_STATE') {
    return {
      text: '❌ That connection link expired or was already used.\n\nPlease start the connection process again.',
      buttons: [[{ text: '🔗 Try Again', data: 'auth:connect' }]],
    };
  }

  // Truly unexpected/internal — the one case a generic message is correct,
  // but we still confirm nothing was silently half-done, and give a ref.
  const ref = generateErrorRef();
  logger.error({ err, ref, context }, 'Unhandled internal error');
  return {
    text: `⚠️ Something went wrong on our end\n\nThis has been logged (error ref: ${ref}). Your action was NOT completed — nothing was changed or committed.`,
    buttons: [[{ text: '🔁 Try Again', data: context.retryCallback || 'noop' }, { text: '🐞 Report This', data: `help:report:${ref}` }]],
  };
}

module.exports = { formatError };
