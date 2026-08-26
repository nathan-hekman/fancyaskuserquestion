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
          {"icon": "tag", "k": "Cost", "v": "$42.00"},
          {"icon": "offer", "k": "Live offer", "v": "$38.62", "tone": "warn", "vt": "down"}
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

Facts are revealed in order, one per sentence of `say`. A series with
`cueFact: n` draws its trendline when fact n lands. Two options are appended to
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
    """Settings written by /fancyquestions. Absent or unreadable means defaults."""
    path = Path.home() / ".config" / "fancyquestions" / "config.json"
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

    Returns (data_uri, [cue_seconds]) — one cue per sentence, so a caller can
    hang a visual on the moment a given sentence starts. Returns (None, [])
    when no speech synthesiser is available; the deck still works, silently.
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
        cues.append(round(at, 2))
        at += duration(clip) + gap
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

            # each fact lands on its own sentence; extras land on the last one
            facts = card.get("facts") or []
            for i, fact in enumerate(facts):
                if "t" not in fact:
                    fact["t"] = cues[i] if i < len(cues) else (cues[-1] if cues else 0)
            card["facts"] = facts

            chart = card.get("chart")
            if chart:
                for series in chart.get("series", []):
                    if "cueAt" in series:
                        continue
                    idx = series.get("cueFact")
                    series["cueAt"] = (facts[idx]["t"] if isinstance(idx, int)
                                       and 0 <= idx < len(facts) else 0)
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
    html = (html.replace("CARDS_JSON", json.dumps(cards))
                .replace("CLIPS_JSON", json.dumps(clips))
                .replace("ANSWERS_JSON", "ANSWERS_JSON_PLACEHOLDER"))

    full = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '</head><body>' + html + '</body></html>')
    # a </script> inside the embedded copy would close the real tag
    source_literal = json.dumps(full).replace("</", "<\\/")
    page = html.replace("ANSWERS_JSON_PLACEHOLDER", json.dumps(answers), 1)
    page = page.replace("var answers = " + json.dumps(answers) + ";",
                        "var answers = " + json.dumps(answers) + ";\n"
                        "var SOURCE = " + source_literal + ";", 1)

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
