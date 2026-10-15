#!/bin/bash
# install.sh — registers the native messaging host with every Chromium-based
# browser it finds (Brave, Chrome, Chromium, Vivaldi, Edge).
#
# The extension ID below is fixed: extension/manifest.json pins a "key", so
# the ID is the same on every machine and no longer depends on where the
# folder lives. Only set EXT_ID yourself if you changed that key.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
HOST_PY="$ROOT_DIR/native/host.py"
MANIFEST="$ROOT_DIR/native/com.ytdlbridge.host.json"
EXT_ID="${EXT_ID:-pflffcomdgpcbbgllmaomoflhbigmohf}"

# label | browser config dir (a NativeMessagingHosts folder goes inside it)
BROWSERS=(
  "Brave|$HOME/.config/BraveSoftware/Brave-Browser"
  "Chrome|$HOME/.config/google-chrome"
  "Chromium|$HOME/.config/chromium"
  "Vivaldi|$HOME/.config/vivaldi"
  "Edge|$HOME/.config/microsoft-edge"
)

chmod +x "$HOST_PY"

# write the manifest with the real path to host.py
cat > "$MANIFEST" << JSON
{
  "name": "com.ytdlbridge.host",
  "description": "Native host for ytdl-bridge",
  "path": "$HOST_PY",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
JSON

echo ""
echo "ytdl-bridge: registering the native host"
echo ""

FOUND=0
for entry in "${BROWSERS[@]}"; do
  label="${entry%%|*}"
  dir="${entry#*|}"
  if [ -d "$dir" ]; then
    mkdir -p "$dir/NativeMessagingHosts"
    cp "$MANIFEST" "$dir/NativeMessagingHosts/com.ytdlbridge.host.json"
    echo "  registered with $label"
    FOUND=1
  fi
done

if [ "$FOUND" -eq 0 ]; then
  echo "  no supported browser found (looked for Brave, Chrome, Chromium, Vivaldi, Edge)."
  echo "  copy $MANIFEST into your browser's NativeMessagingHosts folder by hand."
  exit 1
fi

echo ""
echo "Done. Now:"
echo "  1. Load the extension: open brave://extensions (or chrome://extensions),"
echo "     turn on Developer mode, Load unpacked, pick the 'extension' folder."
echo "  2. Fully restart the browser."
echo "  3. Check config.ini in the repo root before your first download:"
echo "       cookies_from = which browser holds your YouTube login (default: brave)"
echo "       music_dir / video_dir = where downloads go (default: ~/Music, ~/Videos)"
echo "     Put your own values in config.local.ini so updates never overwrite them."
echo ""
