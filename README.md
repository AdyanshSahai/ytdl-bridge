# YT Downloader v3.0

## What's new in this version
- 🔔 **Desktop notification** when a download/batch finishes (needs `notify-send`)
- 📡 **Auto-detects** single video vs playlist vs channel, badge shown in popup
- 📁 **Auto-named folders** — playlists/channels default to their own folder
  named after the channel or playlist title (no more generic `yt-rips` mixing
  everything together). Pick "Custom folder name" to override.
- ⌨️ **Keyboard shortcut** — `Ctrl+Shift+Y` opens the popup without clicking
- 📊 **Clean progress line** — `[42/249] Video Title — 34% (12.1MB/s)`
  instead of yt-dlp's full verbose scroll
- 🍪 **Batched cookie refresh** — long playlists/channels download in
  batches of 10, restarting yt-dlp between batches so cookies never go stale
- 🎨 New icon based on your uploaded SVG, recolored purple to match the rice

## Setup (one time)

### 1. Load the extension
1. Open Brave → `brave://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Copy the **Extension ID**

### 2. Install the native host
```bash
cd native/
bash install.sh
```
Paste your Extension ID when prompted, then restart Brave.

### 3. (Optional) Desktop notifications
Make sure `notify-send` is installed — it ships by default on most KDE/GNOME
setups. Check with:
```bash
which notify-send
```

---

## How to use
- **Click extension icon** (or press `Ctrl+Shift+Y`) → pick Audio or Video
- **Single video** → downloads immediately, no popups
- **Playlist or channel** (`&list=` URL, or `/@handle/videos` etc) →
  - **Where popup** — Default (auto-named) or type a custom folder name
  - **How many popup** — Entire playlist / Just this video / First X items
- **Right-click extension icon** → quick Audio/Video download, full length,
  auto-named folder, no popups

## Requirements
- `ydl-audio` and `yt-dlp` on PATH
- A terminal emulator: konsole, gnome-terminal, xfce4-terminal, or xterm
- `notify-send` for desktop notifications (optional)
