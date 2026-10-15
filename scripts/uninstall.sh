#!/bin/bash
# uninstall.sh — removes what install.sh put on your system. Your downloads
# and this folder are left alone. Remove the extension itself in your
# browser's extensions page.

for dir in \
  "$HOME/.config/BraveSoftware/Brave-Browser" \
  "$HOME/.config/google-chrome" \
  "$HOME/.config/chromium" \
  "$HOME/.config/vivaldi" \
  "$HOME/.config/microsoft-edge"; do
  f="$dir/NativeMessagingHosts/com.ytdlbridge.host.json"
  if [ -f "$f" ]; then
    rm -f "$f" && echo "removed $f"
  fi
done

rm -rf "$HOME/.local/state/ytdl-host" && echo "removed ~/.local/state/ytdl-host"
echo "Done. Now remove the extension in your browser and delete this folder if you like."
