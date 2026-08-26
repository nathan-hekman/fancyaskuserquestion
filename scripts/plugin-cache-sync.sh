#!/usr/bin/env bash
# Mirror this repo into the Claude Code plugin cache after every commit.
#
# Slash commands and skills run from the cache, not from here, so an unpushed
# or unsynced edit means the next session runs yesterday's code.
set -uo pipefail
REPO="$(git rev-parse --show-toplevel)"
NAME="fancyquestions"
VERSION="$(python3 -c "import json,sys;print(json.load(open('$REPO/.claude-plugin/plugin.json'))['version'])" 2>/dev/null)"
[ -n "$VERSION" ] || { echo "post-commit: no version in plugin.json; skip"; exit 0; }

DEST="$HOME/.claude/plugins/cache/$NAME/$NAME/$VERSION"
mkdir -p "$DEST" || exit 0
rsync -a --delete \
  --exclude '.git/' --exclude 'deck/' --exclude '__pycache__/' \
  --exclude '.DS_Store' --exclude '*.aiff' --exclude '*.m4a' \
  "$REPO/" "$DEST/" || exit 0
echo "post-commit: $NAME -> cache $VERSION"

# drop stale version directories so the cache never serves two copies
find "$HOME/.claude/plugins/cache/$NAME/$NAME" -mindepth 1 -maxdepth 1 -type d \
  ! -name "$VERSION" -exec rm -rf {} + 2>/dev/null
