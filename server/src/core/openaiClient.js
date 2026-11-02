const { config } = require('../config');
const { createProvider } = require('./provider');
// Upstream module name retained; all models now use the same local-first facade.
const openai = createProvider(config.ai);
module.exports = { openai };
