#!/usr/bin/env node
// faq-activate.js — SessionStart hook.
//
// Prints one status line plus, when the mode is on, the rules Claude follows
// when it has a decision to put in front of you.

const path = require('path');
const fs = require('fs');
const { readConfig } = require('./faq-config');

const cfg = readConfig();

if (cfg.mode === 'off') {
  process.stdout.write('fancyaskuserquestion: off for this session (/faq on to enable).\n');
  process.exit(0);
}

let version = '0.0.0';
try {
  version = JSON.parse(
    fs.readFileSync(path.join(__dirname, '..', '.claude-plugin', 'plugin.json'), 'utf8')
  ).version;
} catch { /* version is cosmetic */ }

const build = path.join(__dirname, '..', 'scripts', 'build_deck.py');

const rules = `
FANCY ASK ACTIVE — mode: ${cfg.mode} · theme: ${cfg.theme} · version: ${version}

When you are about to ask the user to choose between options — an
AskUserQuestion, a plan needing approval, a set of trade-offs, anything where
you would otherwise print a lettered list — build a decision deck instead.

WHEN IT APPLIES
- ${cfg.mode === 'auto'
      ? 'Any decision with ' + cfg.minOptions + '+ real options and enough substance that the user needs evidence to choose.'
      : 'Only when the user asks for one, or invokes /faq <question>.'}
- Skip it for a yes/no with no evidence behind it, for a clarifying question
  mid-task, and any time the user is clearly in a hurry.

HOW
1. Write a spec JSON: one card per question. Per card give it key, name, sub,
   headline (the call and its reason in one sentence), say (what the narration
   reads aloud), facts, an optional chart, and options.
2. Build it:  python3 "${build}" spec.json --out <dir>
   That renders the narration, times each fact and trendline to the sentence
   that mentions it, and writes one self-contained HTML file.
3. Publish the HTML with the Artifact tool, declaring
   capabilities: {"artifact": {}} so the page can send the answers back.
4. Hand the user the link AND print the question in chat under it — card
   number, the call, and the lettered options, a few lines each. The deck is
   the nicer way to answer, never the only way. Then stop and wait.
5. Answers come back either typed in chat (\`1a\`, or \`1a 2c 3b\`) or tapped
   in the deck, which republishes the page — read the artifact and pull
   \`var answers\`. Both bind. Act only on what was actually chosen; an
   unanswered card is not a skip.

RULES THAT MATTER
- Every card carries "I'll talk to Claude about it" and "Other — say it in
  your own words". Whatever comes back under those, open with it.
- The recommendation is advice. Never pre-select, never act on an unanswered
  card, and say plainly which are still open.
- Never let a number on a card be one you have not verified.
- Full spec and field reference: ${path.join(__dirname, '..', 'skills', 'fancy-ask', 'SKILL.md')}
`.trim();

process.stdout.write(rules + '\n');
