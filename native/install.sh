#!/bin/bash
# install.sh — registers the native messaging host on Linux
# Works with Brave and Chrome

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_PY="$SCRIPT_DIR/host.py"
MANIFEST="$SCRIPT_DIR/com.ytdlaudio.host.json"

# Make host.py executable
chmod +x "$HOST_PY"

echo ""
echo "════════════════════════════════════════"
echo "  YT Downloader — Native Host Installer"
echo "════════════════════════════════════════"
echo ""
echo "Step 1: Load the extension in Brave/Chrome:"
echo "  brave://extensions  →  Load unpacked  →  select the 'extension' folder"
echo ""
echo "Step 2: Paste the Extension ID shown on that page."
echo ""
read -p "Extension ID: " EXT_ID

# Write manifest with real path
cat > "$MANIFEST" << JSON
{
  "name": "com.ytdlaudio.host",
  "description": "Native host for YT Downloader",
  "path": "$HOST_PY",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
JSON

# Register for Brave and Chrome
BRAVE_DIR="$HOME/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts"
CHROME_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"

mkdir -p "$BRAVE_DIR" "$CHROME_DIR"
cp "$MANIFEST" "$BRAVE_DIR/com.ytdlaudio.host.json"
cp "$MANIFEST" "$CHROME_DIR/com.ytdlaudio.host.json"

echo ""
echo "✓ Manifest written to:"
echo "  $BRAVE_DIR"
echo "  $CHROME_DIR"
echo ""
echo "✓ Restart Brave/Chrome and try the extension!"
echo ""
