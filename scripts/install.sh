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

# ---- personal settings -> config_local.ini (optional, interactive) ----
LOCAL_INI="$ROOT_DIR/config_local.ini"
CONFIG_INI="$ROOT_DIR/config.ini"

# default value of a key in config.ini
default_of() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" "$CONFIG_INI" | head -n1; }

ask() { # ask "question" "default" -> sets REPLY_VAL (blank answer keeps default)
  local ans
  read -r -p "  $1 [$2]: " ans || ans=""
  REPLY_VAL="${ans:-$2}"
}

echo "Personal settings"
echo "  These go in config_local.ini, which updates never overwrite."
echo ""

if [ ! -t 0 ]; then
  echo "  (not an interactive terminal, skipping. Create $LOCAL_INI by hand if you want one.)"
else
  DO_CONFIG=1
  if [ -f "$LOCAL_INI" ]; then
    read -r -p "  config_local.ini already exists. Replace it? [y/N]: " yn || yn=""
    case "$yn" in [yY]*) ;; *) DO_CONFIG=0; echo "  keeping your existing config_local.ini" ;; esac
  fi

  if [ "$DO_CONFIG" -eq 1 ]; then
    echo "  Press Enter to accept the value in brackets."
    echo ""
    ask "Browser holding your YouTube login (brave, chrome, firefox, edge, ... or none)" "$(default_of cookies_from)"
    COOKIES="$REPLY_VAL"
    ask "Folder for audio downloads" "$(default_of music_dir)"
    MUSIC="$REPLY_VAL"
    ask "Folder for video downloads" "$(default_of video_dir)"
    VIDEO="$REPLY_VAL"

    # only write what differs from config.ini, so future default changes still apply
    OUT=""
    [ "$MUSIC" != "$(default_of music_dir)" ] && OUT+="music_dir = $MUSIC"$'\n'
    [ "$VIDEO" != "$(default_of video_dir)" ] && OUT+="video_dir = $VIDEO"$'\n'
    BODY=""
    [ -n "$OUT" ] && BODY+="[folders]"$'\n'"$OUT"$'\n'
    [ "$COOKIES" != "$(default_of cookies_from)" ] && BODY+="[browser]"$'\n'"cookies_from = $COOKIES"$'\n'

    echo ""
    if [ -n "$BODY" ]; then
      printf '%s' "$BODY" > "$LOCAL_INI"
      echo "  wrote $LOCAL_INI:"
      sed 's/^/    /' "$LOCAL_INI"
    else
      rm -f "$LOCAL_INI"
      echo "  everything matches the defaults, so no config_local.ini was needed."
    fi
  fi
fi
echo ""

echo ""
echo "Done. Now:"
echo "  1. Load the extension: open brave://extensions (or chrome://extensions),"
echo "     turn on Developer mode, Load unpacked, pick the 'extension' folder."
echo "  2. Fully restart the browser."
echo "  3. Other settings (audio/video format, lyrics, batch size) are in config.ini."
echo "     Override any of them in config_local.ini. Changes apply on the next download."
echo ""
