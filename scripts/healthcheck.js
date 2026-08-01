'use strict';

const env = require('../src/config/env');

(async () => {
  try {
    const res = await fetch(`${env.DOMAIN}/health`);
    const data = await res.json();
    console.log(JSON.stringify(data, null, 2));
    process.exit(res.ok ? 0 : 1);
  } catch (err) {
    console.error('Health check failed:', err.message);
    process.exit(1);
  }
})();
