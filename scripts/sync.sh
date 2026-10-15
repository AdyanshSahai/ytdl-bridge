#!/usr/bin/env bash
# sync.sh — copies your music folder to an Android phone over USB (MTP).
# Optional extra: needs jmtpfs and rsync. Run it from the extension's
# right-click menu ("Sync music to phone") or directly:  bash scripts/sync.sh
#
# Settings come from config.ini / config_local.ini ([folders] music_dir and
# the [sync] section). Phone: unlocked, USB mode set to "File transfer".

set -uo pipefail

ROOT_DIR="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

# read "music_dir | mount_point | phone_dir | delete" the same way host.py does
# (config.ini first, then config_local.ini on top)
IFS='|' read -r SRC MOUNT_POINT PHONE_DIR DELETE < <(python3 -I - "$ROOT_DIR" <<'PY'
import configparser, os, sys
root = sys.argv[1]
cp = configparser.ConfigParser(interpolation=None)
cp.read([os.path.join(root, 'config.ini'), os.path.join(root, 'config_local.ini')], encoding='utf-8')
g = lambda s, k: cp.get(s, k, fallback='').strip()
print('|'.join([os.path.expanduser(g('folders', 'music_dir') or '~/Music'),
                os.path.expanduser(g('sync', 'mount_point') or '~/phone'),
                g('sync', 'phone_dir') or 'Internal shared storage/Music',
                g('sync', 'delete').lower() or 'true']))
PY
)

SRC="${SRC%/}/"                       # trailing slash: copy the contents, not the folder
DEST="$MOUNT_POINT/$PHONE_DIR"
FAILED=0

fail() { echo; echo "ERROR: $1"; FAILED=1; }

notify() {
  command -v notify-send >/dev/null 2>&1 && notify-send -a "ytdl-bridge" -- "$1" "$2" || true
}

finish() {
  if [ "$FAILED" -ne 0 ]; then
    notify "Phone sync failed" "check the terminal"
    echo; echo "Press enter to close."; read -r
    exit 1
  fi
  notify "Phone sync finished" "$SRC -> $PHONE_DIR"
  exit 0
}

for tool in jmtpfs rsync; do
  command -v "$tool" >/dev/null 2>&1 || { fail "'$tool' is not installed."; finish; }
done
[ -d "$SRC" ] || { fail "music folder $SRC does not exist (music_dir in config)."; finish; }

echo "Syncing $SRC"
echo "     to $DEST"
echo

# kill anything that might be holding the USB interface first
pkill -f gvfsd-mtp 2>/dev/null || true
pkill -f kiod 2>/dev/null || true
pkill -f mtp-probe 2>/dev/null || true

# unmount any stale mount (fails harmlessly if nothing's mounted)
fusermount -u "$MOUNT_POINT" 2>/dev/null || true

mkdir -p "$MOUNT_POINT"
jmtpfs "$MOUNT_POINT" || { fail "could not mount the phone. Unlock it and set USB mode to File transfer."; finish; }

# give it a beat to settle before hammering it with rsync
sleep 1

[ -d "$DEST" ] || { fail "'$PHONE_DIR' not found on the phone (phone_dir in config)."; fusermount -u "$MOUNT_POINT" 2>/dev/null; finish; }

RSYNC_ARGS=(-avh --progress --stats --size-only --inplace --modify-window=2
  --exclude='*.py' --exclude='*.ini' --exclude='.*' --exclude='*.temp*'
  --exclude='*.tmp*' --exclude='*.sh*' --exclude='*Misc*')
case "$DELETE" in true|1|yes|on) RSYNC_ARGS+=(--delete) ;; esac

rsync "${RSYNC_ARGS[@]}" "$SRC" "$DEST" || FAILED=1

fusermount -u "$MOUNT_POINT" 2>/dev/null || true
[ "$FAILED" -ne 0 ] && echo "rsync reported errors (see above)."
finish
