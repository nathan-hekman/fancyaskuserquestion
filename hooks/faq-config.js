// faq-config.js — shared config for fancyaskuserquestion.
//
// Settings live in one JSON file so the hook, the slash command and the build
// script all read the same thing. Nothing here touches the network.

const fs = require('fs');
const os = require('os');
const path = require('path');

const VALID_MODES = ['auto', 'manual', 'off'];

function configDir() {
  return path.join(os.homedir(), '.config', 'fancyaskuserquestion');
}

function configPath() {
  return path.join(configDir(), 'config.json');
}

const DEFAULTS = {
  mode: 'auto',          // auto = use a deck whenever a decision comes up
  voice: '',             // empty = the platform's default speaking voice
  rate: 172,             // words per minute
  theme: 'auto',         // auto | light | dark
  minOptions: 2,         // decisions with fewer options stay plain text
  narrate: true          // false = visuals only, no audio
};

function readConfig() {
  try {
    const raw = JSON.parse(fs.readFileSync(configPath(), 'utf8'));
    return Object.assign({}, DEFAULTS, raw);
  } catch {
    return Object.assign({}, DEFAULTS);
  }
}

function writeConfig(patch) {
  const next = Object.assign(readConfig(), patch);
  try {
    fs.mkdirSync(configDir(), { recursive: true });
    fs.writeFileSync(configPath(), JSON.stringify(next, null, 2) + '\n', { mode: 0o600 });
  } catch {
    // A read-only home is not a reason to break the session.
  }
  return next;
}

module.exports = { VALID_MODES, DEFAULTS, configDir, configPath, readConfig, writeConfig };
