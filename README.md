# ytdl-bridge

One-click yt-dlp frontend for Brave/Chrome — a browser extension hands the page you're on to a Python native messaging host, which runs yt-dlp in a terminal window with live progress, batching and desktop notifications.

![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Browser](https://img.shields.io/badge/browser-Brave%20%7C%20Chrome-orange)
![Manifest](https://img.shields.io/badge/extension-MV3-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Table of Contents
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Downloading](#downloading)
- [Popup Options](#popup-options)
- [Terminal Output](#terminal-output)
- [Message Format](#message-format)
- [Configuration](#configuration)
- [Design Notes](#design-notes)
- [Known Issues](#known-issues)
- [Planned Updates](#planned-updates)
- [License](#license)

## How It Works

```
popup / right-click menu
        │  chrome.runtime.sendNativeMessage({url, mode, where, folder, limit, forceSingle})
        ▼
native/host.py ── builds a bash script ──▶ terminal ──▶ yt-dlp, in batches
        │
   replies {status: ok} and exits
```

1. On a YouTube or YT Music page, click the extension (or press `Ctrl+Shift+Y`). The popup works out whether the page is a single video, a playlist or a channel.
2. The extension sends the job to the native host over stdin (4-byte length prefix + JSON).
3. `host.py` generates a bash script, launches it in a terminal, replies `{status: ok}` and exits. The terminal runs detached, so closing the popup or the browser doesn't stop a download.
4. The terminal closes itself after a clean run and stays open on any error.

Audio mode (YT Music pages) rips to Opus with cleaned-up title and artist tags. Video mode (YouTube pages) merges to MKV with English subs embedded.

This is a frontend for [yt-dlp](https://github.com/yt-dlp/yt-dlp), not a replacement. It is a personal tool shared as-is: only download content you have the right to download, and respect the terms of the sites you use it on.

## Requirements

| Dependency | Notes |
|---|---|
| Linux | developed on Fedora KDE (Wayland) |
| Brave or Chrome | any Chromium browser with MV3 support |
| yt-dlp + ffmpeg | on `PATH` |
| Python 3 | for the native host |
| Terminal emulator | konsole, gnome-terminal, xfce4-terminal or xterm, tried in that order |
| notify-send or kdialog | for the finished notification |
| mutagen + syncedlyrics | optional, for lyrics in audio mode: `pip install --user mutagen syncedlyrics` |

yt-dlp reads your YouTube login cookies from a browser, and that defaults to Brave. Using Chrome (or anything else)? Change `cookies_from` in [config.ini](config.ini). See [Configuration](#configuration).

## Installation

```bash
# Clone the repository
git clone https://github.com/AdyanshSahai/ytdl-bridge
cd ytdl-bridge
```

Load the extension:

1. Open `brave://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. Click **Load unpacked** and select the `extension/` folder
4. Copy the **Extension ID**

Register the native host:

```bash
bash native/install.sh
```

Paste the Extension ID when asked, then restart the browser.

**Before the first download**, open [config.ini](config.ini) and check two things: the browser your YouTube login is in (`cookies_from`, default `brave`) and where files should go (`music_dir` and `video_dir`, default `~/Music` and `~/Videos`). Put your own values in `config.local.ini` so updates never overwrite them. Details in [Configuration](#configuration). The script writes `com.ytdlaudio.host.json` (gitignored, since it contains your local path) into the NativeMessagingHosts folders for Brave and Chrome.

Optionally keep yt-dlp current — this checks the installed vs latest version and updates through pip only if outdated:

```bash
bash native/update.sh
```

## Downloading

Open a YouTube or YT Music page, then:

1. Click the extension icon (or press `Ctrl+Shift+Y`).
2. Pick **Audio** or **Video**. The site decides which one is highlighted: `music.youtube.com` is audio, `youtube.com` is video.
3. On a single video, the download starts immediately.
4. On a playlist or channel (`?list=` URLs, or `/@handle/videos`, `/channel/...`, `/c/...`, `/user/...`), choose where to save and how many items, then confirm.
5. A terminal opens and runs the job. A desktop notification fires when it finishes.

Right-click the icon for a quick Audio/Video download: full length, auto-named folder, no popups.

If the run is clean, the terminal closes itself. If anything goes wrong (yt-dlp exit code or `ERROR` line, lyrics failure, notification failure, nothing saved), it stays open so you can read it.

## Popup Options

Where to save:

| Option | Result |
|---|---|
| yt-rips (flat default) | everything in one `yt-rips` folder |
| Auto-named | a folder named after the playlist (or channel) |
| Custom folder name | whatever you type (quotes, backticks, `$`, backslashes and `/` are stripped) |

How many:

| Option | Result |
|---|---|
| Just this video | only the open video, ignoring the playlist it's in |
| Entire playlist | the whole thing, in batches |
| First X items | the first X, in batches |

On a bare playlist/channel page with nothing playing, "Just this video" is hidden and the default becomes the whole thing. On YT Music, where playing a song from a playlist page leaves the URL on `/playlist?list=...`, the popup reads the real playing video ID from the player.

## Terminal Output

yt-dlp runs quiet and prints one line before and after each item, with a progress line that rewrites itself in place in between:

```
[3/42] Downloading: Song Title
    34.2%  12.1MiB/s  eta 00:08
[3/42] Saved: Song Title
```

`[index/count]` shows `-` when yt-dlp doesn't know the playlist size. Titles are cut at 60 characters.

## Message Format

The extension sends one JSON message per job to the native host:

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "mode": "audio",
  "where": "custom",
  "folder": "My Mix",
  "limit": null,
  "forceSingle": true
}
```

- `mode` — `audio` (Opus) or `video` (MKV)
- `where` — `flat` (the flat default folder), `auto` (yt-dlp's `%(playlist_title,channel,uploader|Misc)s` template, so each playlist or channel gets its own folder) or `custom`
- `folder` — the name typed for `custom`. The host strips quotes, backticks, `$`, backslashes, `/` and `%`, and falls back to the flat folder if nothing usable is left, so a name like `..` can't climb out of the music or video folder
- `limit` — integer or `null`, for "first X items"
- `forceSingle` — `true` adds `--no-playlist`, so a `watch?v=..&list=..` URL downloads only that video

## Configuration

Every setting lives in [config.ini](config.ini). To keep your own values, create `config.local.ini` next to it (gitignored) containing only the lines you want to change, for example:

```ini
[folders]
music_dir = /data/Music
video_dir = /data/Videos

[browser]
cookies_from = chrome
```

Changes apply on the next download, with no browser restart. A missing or unreadable value falls back to its default.

| Section | Key | Default | What it does |
|---|---|---|---|
| `folders` | `music_dir` | `~/Music` | where audio downloads go |
| `folders` | `video_dir` | `~/Videos` | where video downloads go |
| `folders` | `flat_folder` | `yt-rips` | name of the flat default folder inside each of the two above |
| `browser` | `cookies_from` | `brave` | browser yt-dlp reads your YouTube login from: `brave`, `chrome`, `chromium`, `edge`, `firefox`, `opera`, `vivaldi`, `BROWSER:PROFILE`, or `none` |
| `download` | `audio_format` | `bestaudio[abr=128]/bestaudio` | yt-dlp format selector for audio |
| `download` | `video_format` | `bestvideo+bestaudio/best` | yt-dlp format selector for video |
| `download` | `batch_size` | `10` | playlist items per yt-dlp run |
| `download` | `cache_wipe_every` | `10` | wipe yt-dlp's cache every N downloads |
| `lyrics` | `enabled` | `true` | fetch lyrics after each audio download |

The extension itself holds no paths: it tells the host *where* to save (flat, auto-named or custom) and the host builds the real folder from this file.

## Lyrics

In audio mode (and unless `enabled = false` in `config.ini`), `native/add_lyrics.py` fetches lyrics for each song as it finishes downloading and embeds them in the file, using [syncedlyrics](https://github.com/moehmeni/syncedlyrics). It runs from the same folder as `host.py`, so there is nothing to configure. If `mutagen` or `syncedlyrics` isn't installed, lyrics are skipped with a one-line note and the run still counts as clean. If the script runs and fails, the terminal stays open.

It also works on its own, for songs you already have:

```bash
python3 native/add_lyrics.py --music-dir ~/Music --whitelist yt-rips
```

`--music-dir` defaults to `$YTDL_MUSIC_DIR`, then `~/Music`. `--blacklist NAME` (repeatable) skips folders.

## Tools

`tools/clean_names.py` strips YouTube junk out of filenames and title tags for files that are already downloaded. It does a dry run unless you pass `--apply`:

```bash
python3 tools/clean_names.py ~/Music/yt-rips -r
```

It is not the same rule set as `host.py`. `host.py` only strips brackets that contain junk words like `(Official Video)` or `[4K]`, so `Song (Krono Remix)` keeps its remix tag. `clean_names.py` strips all bracketed text, so that file would become `Song`.

## Design Notes

- **Playlists run in batches of 10.** `--cookies-from-browser` reads cookies once per yt-dlp process, and they went stale after about 13-14 items in testing. 10 gives margin without much per-batch overhead, with a random 2-3 s pause between batches.
- **Per-run `--download-archive` temp file.** A video listed twice in one playlist downloads once. The file is deleted after the run so it never blocks a later re-download. (Repeats used to crash yt-dlp with "list index out of range".)
- **stdout is never piped.** yt-dlp only rewrites the progress line in place on a real tty. stderr goes to a temp file per batch so `ERROR` lines can be detected.
- **Title cleanup at download time.** `--parse-metadata` splits `Artist - Song` and `--replace-in-metadata` strips bracketed junk like `(Official Video)`, so filename, title tag and artist tag come out clean.
- **Lyrics in the background.** In audio mode, `add_lyrics.py` follows the list of finished files while downloads continue. Its output goes to a log shown afterwards, so it can't mangle the progress line.
- **Terminal closes on a clean run, stays open on any error** (yt-dlp exit code or `ERROR` line, lyrics failure, notification failure, nothing saved).
- **yt-dlp cache wiped every 10 runs.** The counter lives in `~/.local/state/ytdl-host/run_count`.
- **Format-retry loop for singles.** On "Requested format is not available" the terminal lists formats and lets you paste one to retry with.

## Known Issues

- `ERROR` lines print at the end of each batch with only a video ID, not inline at the failing item.
- The flat `yt-rips` folder is named by cleaned title only, so different songs with the same title (or a remaster and the original) can silently fail to save.
- The `Artist - Song` split is a guess; `Song - Live at X` gets the wrong artist.
- With an unknown playlist size, a batch that adds zero files ends the loop, so 10 private/repeat items in a row stops it early.
- No `trap` cleanup if the terminal is closed mid-run.
- Some playlist tracks are region-blocked and need a VPN.

## Planned Updates

- Move the extension ID into the config too, so the installer doesn't have to ask.
- Show errors inline with title and index instead of at the end of a batch.
- Avoid filename collisions in the flat folder.
- Share the channel regex between `popup.js`, `background.js` and `host.py` instead of duplicating it.
- Add a screenshot or GIF of it in action.

Feel free to contribute via forks and Pull Requests, or open an issue if something breaks.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
