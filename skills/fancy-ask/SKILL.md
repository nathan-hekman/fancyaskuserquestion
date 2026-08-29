---
name: fancy-ask
description: Use when about to ask the user to choose between options — an AskUserQuestion, a plan awaiting approval, a set of trade-offs, any lettered list of choices. Builds a narrated, animated card deck the user swipes through, and reads their answers back.
version: 0.1.0
---

# Fancy ask — a decision deck instead of a list

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

## Say it in chat as well

Hand over the link **and print the question in the chat underneath it**, so the
deck is a nicer way to answer, never the only way. Someone at a keyboard should
not have to open a page to reply, and a link that fails to load should not cost
them the question.

Keep the chat copy to a few lines per card — the deck carries the evidence:

```
**1. Redis or Postgres for the session cache**
Take Redis — it holds p95 under 4ms at our peak, where Postgres crosses 40ms.
  a  Redis — $14/mo, p95 under 4ms   (recommended)
  b  Stay on Postgres — free, 41ms at peak
  c  Redis for hot keys only — half the cost, more code
  e  Talk it through with me
  f  Something else — just say it

Answer either way: tap the deck, or type `1a` here. Several at once is fine:
`1a 2c 3b`.
```

Number the cards by position — 1, 2, 3 — matching what the deck shows, and use
the same letters. Then **stop and wait**. Do not proceed as though it were
answered.

## Reading the answers

Answers arrive one of two ways, and both are equally binding: typed in chat
(`1a`, or `1a 2c 3b`), or tapped in the deck and sent, which republishes the
page with the picks baked in and reaches you as a notification.

For a typed answer, echo what you are about to do before doing it. For a
tapped one, Read the artifact and find the picks in the JSON block it carries:

    <script id="deck-answers" type="application/json">{"1":"a"}</script>

A page with no such block was never sent — its built-in `var answers = {}` is
the empty map it was built with, not an answer. Act on the block:

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

`/faq` shows the current settings. `/faq off` disables the deck for the session;
`/faq voice <name>` picks a speaking voice (`say -v '?'` lists them on macOS);
`/faq narrate off` builds silent decks; `/faq manual` stops offering decks
unless asked.

## Requirements

macOS `say` for narration and `ffmpeg` to stitch the clips. Without them the
deck builds silently, and everything except the audio still works.
