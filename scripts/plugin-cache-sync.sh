#!/usr/bin/env bash
# Mirror this repo into the Claude Code plugin cache after every commit.
#
# Slash commands and skills run from the cache, not from here, so an unpushed
# or unsynced edit means the next session runs yesterday's code.
set -uo pipefail
REPO="$(git rev-parse --show-toplevel)"
NAME="fancyaskuserquestion"
VERSION="$(python3 -c "import json,sys;print(json.load(open('$REPO/.claude-plugin/plugin.json'))['version'])" 2>/dev/null)"
[ -n "$VERSION" ] || { echo "post-commit: no version in plugin.json; skip"; exit 0; }

DEST="$HOME/.claude/plugins/cache/$NAME/$NAME/$VERSION"
mkdir -p "$DEST" || exit 0
rsync -a --delete \
  --exclude '.git/' --exclude 'deck/' --exclude '__pycache__/' \
  --exclude '.DS_Store' --exclude '*.aiff' --exclude '*.m4a' \
  "$REPO/" "$DEST/" || exit 0
echo "post-commit: $NAME -> cache $VERSION"

# Point the install registry at this version BEFORE the prune below deletes
# the old directory. On 2026-10-14 a 0.6.0 -> 0.6.1 bump pruned 0.6.0 while
# installed_plugins.json still named it, which leaves new sessions without the
# plugin. Same block as scrape-collection's plugin-cache-sync.sh.
INSTALLED="$HOME/.claude/plugins/installed_plugins.json"
if [ -f "$INSTALLED" ]; then
  python3 - "$INSTALLED" "$NAME" "$VERSION" "$DEST" "$(git rev-parse HEAD)" <<'PY' || exit 0
import json, sys, os, shutil, datetime
ip, name, version, dest, sha = sys.argv[1:6]
d = json.load(open(ip))
ents = d.get("plugins", {}).get(f"{name}@{name}")
if ents:
    shutil.copy2(ip, ip + ".bak")
    for e in ents:
        e["installPath"] = dest
        e["version"] = version
        e["gitCommitSha"] = sha
        e["lastUpdated"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    tmp = ip + ".tmp"
    json.dump(d, open(tmp, "w"), indent=2)
    os.replace(tmp, ip)
    print(f"  install registry -> {name} {version}")
PY
fi

# drop stale version directories so the cache never serves two copies
find "$HOME/.claude/plugins/cache/$NAME/$NAME" -mindepth 1 -maxdepth 1 -type d \
  ! -name "$VERSION" -exec rm -rf {} + 2>/dev/null
