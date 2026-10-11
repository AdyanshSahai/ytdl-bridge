#!/bin/bash
# update_ytdlp.sh — shows current vs latest yt-dlp version, updates via pip
# only if outdated, then confirms the result.
#
# Confirmed install method: pip (user-site, ~/.local/lib/python3.14/site-packages).
#
# Two things this guards against:
#  1. yt-dlp's own --version and PyPI's info.version report the same release
#     with different zero-padding (2026.08.19 vs 2026.8.19) — comparing those
#     strings directly false-positives as "outdated" every run. Both are
#     normalized (leading zeros stripped per dot-segment) before comparing.
#  2. `yt-dlp --version` can hang indefinitely on some systems due to a slow
#     pycryptodome GMP-library lookup (ctypes.util.find_library -> ldconfig).
#     Every yt-dlp invocation below is wrapped in `timeout` so the script
#     can't hang forever waiting on it.

set -e

VERSION_TIMEOUT=20  # seconds before we give up on a hung yt-dlp --version

get_current_version() {
  local out
  if ! out="$(timeout "$VERSION_TIMEOUT" yt-dlp --version 2>&1)"; then
    echo "ERROR: 'yt-dlp --version' timed out or failed after ${VERSION_TIMEOUT}s." >&2
    echo "This is a known slow/hanging pycryptodome GMP-lookup issue on some systems," >&2
    echo "not a problem with this script. Try running 'yt-dlp --version' by itself" >&2
    echo "and waiting it out once, then rerun this script." >&2
    exit 1
  fi
  echo "$out"
}

get_latest_version() {
  python3 -c "
import json, urllib.request
with urllib.request.urlopen('https://pypi.org/pypi/yt-dlp/json', timeout=10) as r:
    data = json.load(r)
print(data['info']['version'])
"
}

normalize_version() {
  # '2026.08.19' and '2026.8.19' both become '2026.8.19'
  python3 -c "print('.'.join(str(int(p)) for p in '$1'.split('.')))"
}

CURRENT="$(get_current_version)"
LATEST="$(get_latest_version)"

echo "Current version: $CURRENT"
echo "Newest version:  $LATEST"

CURRENT_NORM="$(normalize_version "$CURRENT")"
LATEST_NORM="$(normalize_version "$LATEST")"

if [ "$CURRENT_NORM" != "$LATEST_NORM" ]; then
  echo
  echo "Updating to newest version..."
  pip install -U yt-dlp --break-system-packages -q

  CURRENT="$(get_current_version)"
  LATEST="$(get_latest_version)"
  echo
  echo "Current version: $CURRENT"
  echo "Newest version:  $LATEST"
else
  echo
  echo "Already up to date."
fi
