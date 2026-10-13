# 🌉 ytdl-bridge

![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Browser](https://img.shields.io/badge/browser-Brave%20%7C%20Chrome-orange)
![Manifest](https://img.shields.io/badge/extension-MV3-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Click once in your browser, and [yt-dlp](https://github.com/yt-dlp/yt-dlp) does the rest in a terminal window, with live progress and a desktop notification when it's done.

## 🌟 Highlights

- 🖱️ **One click or `Ctrl+Shift+Y`** — no copying URLs, no typing commands
- 🎵 **Audio or video** — YT Music pages rip to Opus, YouTube pages save as MKV with English subs
- 📡 **Knows what you're looking at** — single video, playlist or channel, detected automatically
- 📁 **Tidy folders** — one flat folder, a folder named after the playlist/channel, or your own name
- 🍪 **Handles huge playlists** — batches of 10 so your login cookies never go stale
- 🏷️ **Clean tags** — `Artist - Song (Official Video)` becomes title `Song`, artist `Artist`
- 🔔 **Quiet when it works, loud when it doesn't** — the terminal closes itself after a clean run and stays open on any error

## ℹ️ Overview

ytdl-bridge is a small Chromium extension plus a Python [native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging) host. The extension reads the page you're on and sends it to the host, which builds a bash script and launches it in a terminal. The terminal runs detached, so closing the popup or the browser doesn't stop a download.

It's a frontend for yt-dlp, not a replacement. If you're happy typing `yt-dlp` commands this adds nothing, but if you download from the browser a lot it saves a lot of copy-pasting.

### 👤 Author

Made by [Adyansh Sahai](https://github.com/AdyanshSahai) as a personal tool and shared as-is. Only download content you have the right to download, and respect the terms of the sites you use it on.

## 🚀 Usage

1. Open a YouTube or YT Music page.
2. Click the extension icon (or press `Ctrl+Shift+Y`) and pick **Audio** or **Video**.
3. For a playlist or channel, choose where to save it and how many items you want.

That's it. A terminal opens and shows `[3/42] Downloading: ...` with a progress line that updates in place.

Prefer zero clicks? **Right-click the icon** for a quick Audio/Video download: full length, auto-named folder, no popups.

| Page | Mode |
|---|---|
| `music.youtube.com` | audio (Opus) |
| `youtube.com` | video (MKV) |

## ⬇️ Installation

**Requirements:** Linux, Brave or Chrome, Python 3, `yt-dlp` and `ffmpeg` on your `PATH`, and one terminal emulator (konsole, gnome-terminal, xfce4-terminal or xterm). Developed on Fedora KDE. You also need to be signed in to YouTube in Brave, because yt-dlp reads your cookies from it.

```bash
git clone https://github.com/AdyanshSahai/ytdl-bridge
cd ytdl-bridge
```

**1. Load the extension**
1. Open `brave://extensions` (or `chrome://extensions`) and turn on **Developer mode**
2. Click **Load unpacked** and select the `extension/` folder
3. Copy the **Extension ID** shown on the card

**2. Register the native host**
```bash
bash native/install.sh
```
Paste the Extension ID when asked, then restart the browser.

**3. Keep yt-dlp up to date (optional)**
```bash
bash native/update.sh
```

> The lyrics step in audio mode calls an external `add_lyrics.py` that isn't in this repo yet. See [Configuration](#-configuration).

## 🎛️ Popup options

| Where to save | Result |
|---|---|
| yt-rips (flat default) | everything in one `yt-rips` folder |
| Auto-named | a folder named after the playlist (or channel) |
| Custom folder name | whatever you type |

| How many | Result |
|---|---|
| Just this video | only the open video, ignoring the playlist it's in |
| Entire playlist | the whole thing, in batches |
| First X items | the first X, in batches |

## ⚙️ Configuration

There's no config file yet, so these are hardcoded and need editing for your machine:

| What | Where |
|---|---|
| Music / video base folders | `extension/popup.js`, `extension/background.js`, `native/host.py` |
| Lyrics script path (`LYRICS_SCRIPT`) | `native/host.py` |
| Browser for cookies | `COMMON_ARGS` in `native/host.py` |
| Batch size, cache-wipe interval | `BATCH_SIZE`, `CACHE_WIPE_EVERY` in `native/host.py` |
| Audio / video formats | `DEFAULT_AUDIO_FMT`, `DEFAULT_VIDEO_FMT` in `native/host.py` |

## 🔧 Under the hood

```
popup / right-click menu
        │  chrome.runtime.sendNativeMessage({url, mode, dest, limit, forceSingle})
        ▼
native/host.py ── builds a bash script ──▶ terminal ──▶ yt-dlp, in batches
        │
   replies {status: ok} and exits
```

- **Batches of 10.** `--cookies-from-browser` reads cookies once per yt-dlp process, and they went stale after about 13–14 items in testing. A random 2–3 s pause sits between batches.
- **Per-run `--download-archive` temp file.** A video listed twice in one playlist downloads once. It's deleted afterwards so it never blocks a later re-download.
- **stdout is never piped.** yt-dlp only rewrites the progress line in place on a real tty. stderr goes to a temp file per batch so `ERROR` lines can be detected.
- **Title cleanup at download time** with `--parse-metadata` and `--replace-in-metadata`, so filename and tags come out clean.
- **Lyrics in the background.** In audio mode `add_lyrics.py` follows the list of finished files while downloads continue, logging to a file shown afterwards.
- **yt-dlp cache wiped every 10 runs** (counter in `~/.local/state/ytdl-host/run_count`).
- **Format-retry loop for singles.** On "Requested format is not available" you can paste a different format.

## 🐛 Known issues

- `ERROR` lines print at the end of each batch with only a video ID, not inline at the failing item.
- The flat `yt-rips` folder is named by cleaned title only, so different songs with the same title can silently fail to save.
- The `Artist - Song` split is a guess; `Song - Live at X` gets the wrong artist.
- With an unknown playlist size, a batch that adds zero files ends the loop early.
- No `trap` cleanup if the terminal is closed mid-run.
- `dest` sanitising strips quotes but not `..`.
- Some playlist tracks are region-blocked and need a VPN.

## 🗺️ Planned

- One config for paths, browser and extension ID
- Bring the lyrics script into `native/`
- Inline errors with title and index
- Avoid filename collisions in the flat folder
- A screenshot or GIF of it in action

## 💭 Feedback and contributing

Found a bug or want a feature? [Open an issue](https://github.com/AdyanshSahai/ytdl-bridge/issues). Pull requests from forks are welcome.

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
