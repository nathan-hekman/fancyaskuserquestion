---
description: "Settings for fancyaskuserquestion (auto/manual/off, voice, rate, theme, narrate), or build a decision deck for a question you type."
argument-hint: "status | auto | manual | off | on | voice <name> | voices | rate <n> | narrate on|off | theme dark|light|auto | <a decision to put to me>"
---

Interpret `$ARGUMENTS` as follows. Match exactly — do not be creative.

Settings live in `~/.config/faq/config.json`. Read it, apply
the change, write it back, and confirm in ONE line. Never dump the whole file.

- **empty or `status`** — print the current mode, voice, rate, narrate and
  theme on one line each. Nothing else.

- **`auto`** — set `mode: "auto"`. Confirm: "Fancy ask → auto. Decisions with
  real options get a deck." 

- **`manual`** — set `mode: "manual"`. Confirm: "Fancy ask → manual. I'll ask
  in plain text unless you invoke /faq."

- **`off`** — set `mode: "off"`. Confirm: "Fancy ask off. /faq auto to bring it
  back."

- **`on`** — same as `auto`.

- **`voice <name>`** — set `voice`. On macOS, verify it against
  `say -v '?'` first and say so if it isn't installed. Confirm with a
  three-word sample rendered by that voice if you can play one.

- **`voices`** — run `say -v '?'` and show only the voices for the user's
  language, one per line, name first. No commentary.

- **`rate <n>`** — set `rate` (words per minute, 120-260 is sane).

- **`narrate on|off`** — set `narrate`. Off builds silent decks, which is the
  right setting in a quiet room.

- **`theme dark|light|auto`** — set `theme`.

- **anything else** — treat the whole argument as a decision to put to the
  user. Build a deck for it: work out the real options, gather whatever
  evidence you actually have (never invent numbers), write the spec, run
  `scripts/build_deck.py`, publish it with the Artifact tool declaring
  `capabilities: {"artifact": {}}`, and hand over the link. Then stop and wait.
  The skill `fancy-ask` has the full procedure; follow it rather than
  improvising.
