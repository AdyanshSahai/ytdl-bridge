# ytdl-bridge

One-click [yt-dlp](https://github.com/yt-dlp/yt-dlp) frontend for Brave/Chrome — a browser extension hands the page you're on to a Python native messaging host, which runs yt-dlp in a terminal window with live progress, batching and desktop notifications.

![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Browser](https://img.shields.io/badge/browser-Brave%20%7C%20Chrome-orange)
![Manifest](https://img.shields.io/badge/extension-MV3-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

> Personal tool, shared as-is. Only download content you have the right to download, and respect the terms of the sites you use it on.

## Table of Contents
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Using It](#using-it)
- [Popup Options](#popup-options)
- [Message Format](#message-format)
- [Design Notes](#design-notes)
- [Configuration](#configuration)
- [Known Issues](#known-issues)
- [Planned Updates](#planned-updates)
- [License](#license)

## How It Works

```
popup / right-click menu
        │  chrome.runtime.sendNativeMessage
        ▼
native/host.py   ── builds a bash script ──▶  terminal (konsole / gnome-terminal / xfce4-terminal / xterm)
        │                                              │
   replies {status: ok}                          yt-dlp, in batches
   and exits                                     progress + notification
```

1. On a YouTube or YT Music page you click the extension (or press `Ctrl+Shift+Y`). The popup works out whether the page is a single video, a playlist or a channel.
2. The extension sends `{url, mode, dest, limit, forceSingle}` to the native host over stdin (4-byte length prefix + JSON).
3. `host.py` generates a bash script, launches it in a terminal, replies `{status: ok}` and exits. The terminal runs detached, so closing the popup or browser doesn't kill the download.
4. The terminal closes itself after a clean run and **stays open on any error** so you can read it.

Audio mode (YT Music pages) rips to Opus with cleaned-up title/artist tags. Video mode (YouTube pages) merges to MKV with English subs embedded.

## Requirements

| Dependency | Notes |
|---|---|
| Linux | developed on Fedora KDE (Wayland) |
| Brave or Chrome | any Chromium browser with MV3 support |
| `yt-dlp` | on `PATH`, plus `ffmpeg` |
| Python 3 | for the native host |
| A terminal emulator | konsole, gnome-terminal, xfce4-terminal or xterm (tried in that order) |
| `notify-send` or `kdialog` | for the finished notification (optional, but a missing one counts as an error) |

yt-dlp reads your login cookies with `--cookies-from-browser brave`, so you need to be signed in to YouTube in Brave. If you use Chrome, change that argument in `native/host.py`.

## Installation

```bash
# Clone the repository
git clone https://github.com/AdyanshSahai/ytdl-bridge
cd ytdl-bridge
```

**1. Load the extension**
1. Open `brave://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. **Load unpacked** → select the `extension/` folder
4. Copy the **Extension ID**

**2. Register the native host**
```bash
bash native/install.sh
```
Paste the Extension ID when asked, then restart the browser. The script writes `com.ytdlaudio.host.json` (gitignored — it contains your local path) into the NativeMessagingHosts folders for both Brave and Chrome.

**3. Keep yt-dlp fresh (optional)**
```bash
bash native/update.sh
```
Shows the installed vs latest version and updates through pip only if outdated.

## Using It

- **Click the icon** (or `Ctrl+Shift+Y`) → pick Audio or Video.
- **Single video** → downloads straight away, no extra choices.
- **Playlist or channel** (`?list=` URLs, or `/@handle/videos`, `/channel/...`, `/c/...`, `/user/...`) → pick where to save and how many.
- **Right-click the icon** → quick Audio/Video download, full length, auto-named folder, no popups.

Mode is picked from the site: `music.youtube.com` → audio, `youtube.com` → video.

## Popup Options

**Where to save**

| Option | Result |
|---|---|
| yt-rips (flat default) | everything in one `yt-rips` folder |
| Auto-named | a folder named after the playlist title (or channel) |
| Custom folder name | whatever you type (quotes, backticks, `$`, backslashes and `/` are stripped) |

**How many**

| Option | Result |
|---|---|
| Just this video | downloads only the open video, ignoring the playlist it's in |
| Entire playlist | the whole thing, in batches |
| First X items | the first X, in batches |

On a bare playlist/channel page with no video playing, "Just this video" is hidden and the default becomes the whole thing. On YT Music, where playing a song from a playlist page leaves the URL on `/playlist?list=...`, the popup reads the real playing video ID from the player.

## Message Format

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "mode": "audio",
  "dest": "/path/to/Music/yt-rips",
  "limit": null,
  "forceSingle": true
}
```

| Field | Meaning |
|---|---|
| `mode` | `audio` (Opus) or `video` (MKV) |
| `dest` | output folder. A trailing `/__AUTO__` becomes yt-dlp's `%(playlist_title,channel,uploader\|Misc)s` template |
| `limit` | integer or `null` — "first X items" |
| `forceSingle` | `true` adds `--no-playlist`, so a `watch?v=..&list=..` URL downloads one video |

## Design Notes

- **Playlists run in batches of 10.** `--cookies-from-browser` reads cookies once per yt-dlp process, and they went stale after about 13–14 items in testing. 10 gives margin without much per-batch overhead, with a random 2–3 s pause between batches.
- **Per-run `--download-archive` temp file.** A video listed twice in one playlist downloads once. The file is deleted after the run so it never blocks a later re-download. (Repeats used to crash yt-dlp with "list index out of range".)
- **stdout is never piped.** yt-dlp only rewrites the progress line in place on a real tty. stderr goes to a temp file per batch so `ERROR` lines can be detected.
- **Title cleanup at download time.** `--parse-metadata` splits `Artist - Song` and `--replace-in-metadata` strips bracketed junk like `(Official Video)`, so the filename, title tag and artist tag all come out clean.
- **Lyrics in the background.** In audio mode, `add_lyrics.py` follows the list of finished files while downloads continue. Its output goes to a log shown afterwards, so it can't mangle the progress line.
- **Terminal closes on a clean run, stays open on any error** (yt-dlp exit code or `ERROR` line, lyrics failure, notification failure, nothing saved).
- **yt-dlp cache wiped every 10 runs.** The counter lives in `~/.local/state/ytdl-host/run_count`.
- **Format-retry loop for singles.** On "Requested format is not available" the terminal lists formats and lets you paste one to retry with.

## Configuration

There's no config file yet — these are hardcoded and need editing to match your machine:

| What | Where |
|---|---|
| Music / video base folders | `extension/popup.js`, `extension/background.js`, `native/host.py` |
| Lyrics script path (`LYRICS_SCRIPT`) | `native/host.py` |
| Browser for cookies | `COMMON_ARGS` in `native/host.py` |
| Batch size, cache-wipe interval | `BATCH_SIZE`, `CACHE_WIPE_EVERY` in `native/host.py` |
| Audio / video format strings | `DEFAULT_AUDIO_FMT`, `DEFAULT_VIDEO_FMT` in `native/host.py` |

The lyrics script is not in this repo yet — audio mode expects it at `LYRICS_SCRIPT`.

## Known Issues

- `ERROR` lines print at the end of each batch with only a video ID, not inline at the failing item.
- The flat `yt-rips` folder is named by cleaned title only, so different songs with the same title (or a remaster and the original) can silently fail to save.
- The `Artist - Song` split is a guess — `Song - Live at X` gets the wrong artist.
- With an unknown playlist size, a batch that adds zero files ends the loop, so 10 private/repeat items in a row stops it early.
- No `trap` cleanup if the terminal is closed mid-run.
- `dest` sanitising strips quotes but not `..`.
- The channel regex and base paths are duplicated across `popup.js`, `background.js` and `host.py`.
- Some playlist tracks are region-blocked and need a VPN.

## Planned Updates

- Move the hardcoded paths, browser and extension ID into a single config.
- Bring the lyrics script into `native/`.
- Show errors inline with title and index instead of at the end of a batch.
- Avoid filename collisions in the flat folder.
- Share the channel regex and path logic instead of duplicating it.

Contributions are welcome via forks and Pull Requests.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
