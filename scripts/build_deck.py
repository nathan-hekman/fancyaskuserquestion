#!/usr/bin/env python3
"""Build a narrated, animated decision deck from a spec file.

A deck is one self-contained HTML page: a card per question, narration that
reads each one aloud, facts and trendlines timed to the sentence that mentions
them, and options the reader taps. Publish it with the Artifact tool declaring
capabilities {"artifact": {}} and the answers come back to the session.

    python3 build_deck.py spec.json --out ./deck

Spec (see examples/example-spec.json for a filled-in one):

    {
      "title":  "Four cards left",       # the page name
      "kicker": "Accept-offers",         # small line above it
      "dek":    "Swipe between cards…",  # one sentence of instruction
      "foot":   "Where the numbers came from.",
      "voice":  "Samantha",              # any `say -v '?'` voice; omit for default
      "rate":   172,
      "narrate": true,
      "answers": {"1": "a"},             # pre-filled picks, if any
      "cards": [{
        "key": "1",
        "name": "2024 Pokemon Magneton",
        "sub": "cert 136885983 · PSA 10",
        "image": "path/to.jpg | https://… | null",
        "headline": "The call and its reason, in one sentence with a number.",
        "say": "What the narration reads. One idea per sentence.",
        "facts": [
          {"icon": "tag", "k": "Cost", "v": "$42.00", "cueSentence": 2},
          {"icon": "offer", "k": "Live offer", "v": "$38.62", "tone": "warn",
           "vt": "down", "cueSentence": 2, "cueOffset": 1.4}
        ],
        "chart": {
          "label": "Offer and sales history",
          "unit": "$",
          "marker": {"label": "cost", "value": 42.0},
          "series": [
            {"name": "offer", "color": "plum",   "kind": "line",
             "points": [{"d": "2026-07-08", "v": 44.1}], "cueFact": 1},
            {"name": "sales", "color": "orange", "kind": "points",
             "points": [{"d": "2026-08-23", "v": 55.0}], "cueFact": 2}
          ]
        },
        "options": [
          {"letter": "a", "label": "List at $55", "sub": "160 comps",
           "delta": 3.92, "rec": true}
        ]
      }]
    }

Facts are revealed one per sentence of `say`, in order, and each animates for
as long as its sentence lasts. `cueSentence` pins a fact to a particular
sentence when the script has a lead-in; `cueOffset` (seconds) separates two
facts that share one. A series with `cueFact: n` draws its trendline while fact
n's sentence is being spoken. Two options are appended to
every card automatically: "I'll talk to Claude about it" and "Other".

Icons available: tag offer up down flat bars check clock chat pen ban cart
play redo.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "templates" / "deck.html"

TALK = {"letter": "e", "label": "I'll talk to Claude about it",
        "sub": "Claude opens with this one after you send"}
OTHER = {"letter": "f", "label": "Other — say it in your own words",
         "sub": "type anything; it goes back with your picks"}

SENTENCE = re.compile(r"(?<=[.!?])\s+")


def config() -> dict:
    """Settings written by /faq. Absent or unreadable means defaults."""
    path = Path.home() / ".config" / "fancyaskuserquestion" / "config.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def have(binary: str) -> bool:
    return shutil.which(binary) is not None


def data_uri(source: str | None) -> str | None:
    """Inline an image. A published page cannot fetch a remote host."""
    if not source:
        return None
    try:
        if source.startswith("data:"):
            return source
        if source.startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=25) as fh:
                raw = fh.read()
            kind = mimetypes.guess_type(source)[0] or "image/jpeg"
        else:
            path = Path(source).expanduser()
            raw = path.read_bytes()
            kind = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        if len(raw) > 3_000_000:
            print(f"  ! {source} is {len(raw)//1024}KB — shrink it first", file=sys.stderr)
        return f"data:{kind};base64," + base64.b64encode(raw).decode()
    except Exception as exc:
        print(f"  ! could not inline {source}: {exc}", file=sys.stderr)
        return None


def narrate(text: str, voice: str, rate: int, workdir: Path, stem: str):
    """Speak `text` one sentence at a time and stitch the clips together.

    Returns (data_uri, [{"t": start, "dur": seconds}]) — one entry per
    sentence. A visual hung on a sentence can then last exactly as long as the
    sentence does, which is the whole point of speaking them separately.
    Returns (None, []) when no speech synthesiser is available; the deck still
    works, silently.
    """
    if not text or not have("say") or not have("ffmpeg"):
        if text and not have("say"):
            print("  ! no `say` on this platform — building a silent deck", file=sys.stderr)
        return None, []

    sentences = [s.strip() for s in SENTENCE.split(text) if s.strip()]
    if not sentences:
        return None, []

    clips, cues, at = [], [], 0.0
    gap = 0.22
    for i, sentence in enumerate(sentences):
        clip = workdir / f"{stem}_{i}.aiff"
        cmd = ["say"]
        if voice:
            cmd += ["-v", voice]
        cmd += ["-r", str(rate), "-o", str(clip), sentence]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            print(f"  ! say failed on sentence {i}: {exc.stderr.decode()[:120]}", file=sys.stderr)
            return None, []
        secs = duration(clip)
        cues.append({"t": round(at, 2), "dur": round(secs + gap, 2)})
        at += secs + gap
        clips.append(clip)

    listing = workdir / f"{stem}.txt"
    with listing.open("w") as fh:
        for i, clip in enumerate(clips):
            silence = workdir / f"{stem}_gap{i}.aiff"
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                 "-i", "anullsrc=r=22050:cl=mono", "-t", str(gap),
                 "-c:a", "pcm_s16be", str(silence)], check=True)
            fh.write(f"file '{clip.name}'\nfile '{silence.name}'\n")

    out = workdir / f"{stem}.m4a"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-ar", "44100", "-ac", "1",
         "-c:a", "aac", "-b:a", "64k", str(out)], check=True, cwd=workdir)
    uri = "data:audio/mp4;base64," + base64.b64encode(out.read_bytes()).decode()
    return uri, cues


def duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
        return float(out.stdout.strip())
    except Exception:
        return 3.0


def build(spec: dict, outdir: Path) -> Path:
    cfg = config()
    voice = spec.get("voice", cfg.get("voice", ""))
    rate = int(spec.get("rate", cfg.get("rate", 172)))
    speak = spec.get("narrate", cfg.get("narrate", True))

    cards, clips = [], {}
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for n, raw in enumerate(spec.get("cards", [])):
            card = dict(raw)
            card.setdefault("key", str(n + 1))
            clip_id = "c" + card["key"]
            card["clip"] = clip_id
            card["image"] = data_uri(card.get("image"))

            cues = []
            if speak and card.get("say"):
                uri, cues = narrate(card["say"], voice, rate, work, clip_id)
                if uri:
                    clips[clip_id] = uri
            print(f"  card {card['key']}: {len(cues)} narration cues")

            # A fact lands on the sentence that says it and lasts as long as
            # that sentence. By default that is sentence i — write one idea per
            # sentence, in the same order as the facts, and it lines up. When
            # the script opens with a lead-in ("Card eight."), say which
            # sentence each fact belongs to with cueSentence, and nudge a
            # second fact sharing one sentence with cueOffset.
            facts = card.get("facts") or []
            for i, fact in enumerate(facts):
                idx = fact.get("cueSentence", i)
                cue = cues[idx] if 0 <= idx < len(cues) else (cues[-1] if cues else None)
                offset = float(fact.get("cueOffset", 0))
                if "t" not in fact:
                    fact["t"] = round((cue["t"] if cue else 0) + offset, 2)
                if "dur" not in fact:
                    fact["dur"] = round(max(0.6, (cue["dur"] if cue else 0) - offset), 2)
            card["facts"] = facts

            chart = card.get("chart")
            if chart:
                for series in chart.get("series", []):
                    idx = series.get("cueFact")
                    anchored = (isinstance(idx, int) and 0 <= idx < len(facts))
                    if "cueAt" not in series:
                        series["cueAt"] = facts[idx]["t"] if anchored else 0
                    if "cueDur" not in series:
                        series["cueDur"] = facts[idx].get("dur", 0) if anchored else 0
                card["chart"] = chart

            options = list(card.get("options") or [])
            letters = {o.get("letter") for o in options}
            if "e" not in letters:
                options.append(dict(TALK))
            if "f" not in letters:
                options.append(dict(OTHER))
            card["options"] = options
            cards.append(card)

    html = TEMPLATE.read_text()
    for token, value in (
        ("DECK_TITLE", spec.get("title", "A decision")),
        ("DECK_KICKER", spec.get("kicker", "")),
        ("DECK_DEK", spec.get("dek", "Swipe between cards. Answer any of them, "
                                     "in any order, then send.")),
        ("DECK_FOOT", spec.get("foot", "")),
    ):
        html = html.replace(token, value)

    answers = spec.get("answers") or {}
    seed = json.dumps(answers)
    html = (html.replace("CARDS_JSON", json.dumps(cards))
                .replace("CLIPS_JSON", json.dumps(clips))
                .replace("ANSWERS_JSON", seed))

    # The embedded copy the page republishes when someone sends their picks.
    # Its answers map is real JSON, not a placeholder, so a save that somehow
    # carries no picks still yields a page that opens and can be answered
    # again. The picks ride in a JSON block appended before </body>.
    full = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '</head><body>' + html + '</body></html>')
    if "</body>" not in full:
        raise SystemExit("template lost its </body>; the save path needs it")
    # a </script> inside the embedded copy would close the real tag
    source_literal = json.dumps(full).replace("</", "<\\/")
    marker = "var answers = " + seed + ";"
    if marker not in html:
        raise SystemExit("could not find the answers slot to attach SOURCE to")
    page = html.replace(marker, marker + "\nvar SOURCE = " + source_literal + ";", 1)

    target = outdir / (slug(spec.get("title", "deck")) + ".html")
    target.write_text(page)
    return target


def slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return out or "deck"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="path to the spec JSON, or - for stdin")
    ap.add_argument("--out", default="./deck", help="directory for the built page")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.spec == "-" else Path(args.spec).read_text()
    spec = json.loads(raw)
    if not spec.get("cards"):
        print("spec has no cards", file=sys.stderr)
        return 2

    path = build(spec, Path(args.out).expanduser())
    size = path.stat().st_size
    print(f"\n{path}")
    print(f"{size/1_000_000:.2f} MB — publish it with the Artifact tool, "
          f'capabilities {{"artifact": {{}}}}')
    if size > 16_000_000:
        print("! over the 16MB artifact limit — shorten the narration or the images",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
