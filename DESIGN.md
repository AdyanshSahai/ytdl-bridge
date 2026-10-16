# ytdl-bridge: Design

How ytdl-bridge works under the hood, and why it's built this way. For setup and usage, see the README.

## How It Works

```
popup / right-click menu
        │  chrome.runtime.sendNativeMessage({url, mode, where, folder, limit, forceSingle})
        ▼
native/host.py ── builds a bash script ──▶ terminal ──▶ yt-dlp, in batches
        │
   replies {status: ok} and exits
```

Where things live:

| Folder | What's in it |
|---|---|
| `extension/` | the browser extension (popup, right-click menu, shortcut) |
| `native/` | the native host (`host.py`) and the lyrics script |
| `scripts/` | `install.sh`, `update.sh`, `uninstall.sh`, `sync.sh` |
| `tools/` | optional extras, like the filename cleaner |
| `config.ini` | every setting, in one file |

The extension is a thin frontend. It reads the page you're on and sends the job to a Python [native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging) host over stdin (4-byte length prefix + JSON). The host generates a bash script, launches it in a terminal and exits. The terminal runs detached, so closing the popup or the browser doesn't stop a download. It closes itself after a clean run and stays open on any error.

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

## Terminal Output

yt-dlp runs quiet and prints one line before and after each item, with a progress line that rewrites itself in place in between:

```
[3/42] Downloading: Song Title
    34.2%  12.1MiB/s  eta 00:08
[3/42] Saved: Song Title
```

`[index/count]` shows `-` when yt-dlp doesn't know the playlist size. Titles are cut at 60 characters.

## Design Notes

- **Playlists run in batches of 10.** `--cookies-from-browser` reads cookies once per yt-dlp process, and they went stale after about 13-14 items in testing. 10 gives margin without much per-batch overhead, with a random 2-3 s pause between batches.
- **Per-run `--download-archive` temp file.** A video listed twice in one playlist downloads once. The file is deleted after the run so it never blocks a later re-download. (Repeats used to crash yt-dlp with "list index out of range".)
- **stdout is never piped.** yt-dlp only rewrites the progress line in place on a real tty. stderr goes to a temp file per batch so `ERROR` lines can be detected.
- **Title cleanup at download time.** `--parse-metadata` splits `Artist - Song` and `--replace-in-metadata` strips bracketed junk like `(Official Video)`, so filename, title tag and artist tag come out clean.
- **Lyrics in the background.** In audio mode, `add_lyrics.py` follows the list of finished files while downloads continue. Its output goes to a log shown afterwards, so it can't mangle the progress line.
- **Terminal closes on a clean run, stays open on any error** (yt-dlp exit code or `ERROR` line, lyrics failure, notification failure, nothing saved).
- **yt-dlp cache wiped every 10 runs.** The counter lives in `~/.local/state/ytdl-host/run_count`.
- **Pipe suffixes are stripped.** Titles like `Song | Genre | Channel` keep only `Song`. Only " | " with spaces around it counts, so a title with a bare `|` is left alone.
- **Format-retry loop for singles.** On "Requested format is not available" the terminal lists formats and lets you paste one to retry with.

## Security

The extension talks to a local program, so the doors are worth spelling out:

- **Only this extension can call the host.** The native messaging manifest's `allowed_origins` lists the one fixed extension ID (the `key` in `extension/manifest.json` pins it), so other extensions and web pages can't send it jobs. Nothing listens on a network port.
- **The URL can't inject shell.** `host.py` writes the download as a bash script, and every value that goes into it (URL, folder, format) is passed through `shlex.quote`. The template is filled in a single pass, so a URL that happens to contain a placeholder like `@@BODY@@` stays inside its quotes. Inside the script the URL is only ever used as a quoted `"$URL"`.
- **Folder names are sanitised.** Quotes, backticks, `$`, backslashes, `/` and `%` are stripped, and `..` is rejected, so a custom folder can't leave the music or video folder.
- **Config is trusted.** `config.ini` and `config_local.ini` are yours; `cookies_from` and the format selectors are quoted into the script like every other value.
