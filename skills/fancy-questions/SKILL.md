---
name: fancy-questions
description: Use when about to ask the user to choose between options — an AskUserQuestion, a plan awaiting approval, a set of trade-offs, any lettered list of choices. Builds a narrated, animated card deck the user swipes through, and reads their answers back.
version: 0.1.0
---

# Fancy questions — a decision deck instead of a list

A plain multiple-choice prompt puts the options in front of someone and leaves
the evidence behind. A deck puts both in front of them: the call, the numbers,
a chart, and the options, read aloud in order, on a page they can answer from a
phone.

Use it when the decision has real weight and the user needs evidence to choose.
Skip it for a yes/no with nothing behind it, a clarifying question mid-task, or
any moment the user is clearly in a hurry — a deck takes about twenty seconds
to build and it is worse than a sentence when a sentence would do.

## The shape of one card

Every card answers one question, in this order. The order is the design: the
call comes before the evidence, and the evidence before the options.

1. **Identity** — what this is about, and a quiet sub-line.
2. **The call** — your recommendation and its reason, in ONE sentence with a
   number in it. It renders first, before a word is spoken.
3. **The chart** — optional, but it is what makes a deck worth building.
4. **The facts** — three or four, each an icon, a label and a value.
5. **The options** — what they can actually do, with the cost of each.

## Building one

Write a spec and run the builder. The full field reference is the docstring of
`scripts/build_deck.py`; `examples/example-spec.json` is a working one.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_deck.py" spec.json --out ./deck
```

The builder speaks the `say` text one sentence at a time, so it knows when each
sentence starts. Fact 0 lands on sentence 0, fact 1 on sentence 1, and a chart
series with `cueFact: 2` draws its trendline when fact 2 lands. **Write `say`
with one idea per sentence, in the same order as the facts**, and the timing
works itself out. Nothing else in the deck needs a timestamp.

Then publish it:

```
Artifact(file_path: "./deck/<name>.html", capabilities: {"artifact": {}})
```

The `artifact` capability is what lets the page send answers back. Without it
the deck still renders and the user can copy a key line instead, but nothing
returns to you on its own.

Hand over the link and **stop**. The deck is the question; do not also ask it
in text, and do not proceed as though it were answered.

## Reading the answers

The user taps Send and the page republishes itself with their picks baked in.
That arrives as a republish notification. Read the artifact, find `var answers`,
and act:

- `{"1": "a"}` — they chose option a on card 1.
- `{"2": {"letter": "f", "text": "…"}}` — they wrote their own answer. Read it
  and treat it as the instruction it is.
- Option `e` means they want to talk it through. **Open your reply with those**,
  before reporting anything you executed.
- A card with no entry is **not** a skip. Leave it alone and say plainly that
  it is still open.

Echo what you are about to do before doing it, and never act on a card the user
did not answer.

## Rules

- The recommendation is advice. Never pre-select an option, and never let the
  deck act on its own.
- Every number on a card is one you verified. A deck makes a figure look
  authoritative; that is a reason for more care, not less.
- Money and irreversible actions still need the same confirmation they always
  did. The deck is how you ask, not permission to skip asking.
- Two options are appended to every card automatically — "I'll talk to Claude
  about it" and "Other — say it in your own words". Do not write your own
  versions of them.
- Charts scale to their line series, so one outlier cannot flatten the picture;
  outliers are pinned to the top edge and named, never dropped.
- Everything on the page reveals on its own if audio is blocked. Content never
  waits on sound.

## Settings

`/fancyquestions` shows the current settings. `/fancyquestions off` disables the deck for the session;
`/fancyquestions voice <name>` picks a speaking voice (`say -v '?'` lists them on macOS);
`/fancyquestions narrate off` builds silent decks; `/fancyquestions manual` stops offering decks
unless asked.

## Requirements

macOS `say` for narration and `ffmpeg` to stitch the clips. Without them the
deck builds silently, and everything except the audio still works.
