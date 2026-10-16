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

## Components

| Piece | Owns |
|---|---|
| `extension/popup.js`, `background.js` | reading the page, the popup options, the right-click menu. No paths, no yt-dlp arguments. |
| `native/host.py` | turning a message into a folder, a format and a bash script, and opening a terminal. It exits as soon as the terminal is launched. |
| the generated bash script | the actual run: yt-dlp, batching, error detection, lyrics, the notification. It lives in `/tmp` and deletes itself at the end. |
| `native/add_lyrics.py` | fetching lyrics and writing them into the files. Started by the script, not by the host. |
| `config.ini`, `config_local.ini` | every setting. Read by `host.py` on each message, so changes apply on the next download. |

## Life of a Download

1. The popup works out the mode from the page: `music.youtube.com` is audio, `youtube.com` is video. The right-click menu skips the popup, and you pick audio or video in the menu. On YT Music, where the URL can stay on `/playlist?list=...` while a song plays, the popup asks the page's player for the real video ID.
2. The extension sends one JSON message (see Message Format) and `host.py` reads it from stdin.
3. The host decides whether the job is a playlist or channel: the URL has `list=` or matches a channel pattern, and `forceSingle` is not set. Otherwise it adds `--no-playlist`.
4. It turns `where` and `folder` into a target folder (see Folder Resolution) and picks the format selector for the mode from the config.
5. It fills a bash script template, writes it to a temp file and opens it in the first terminal it finds: konsole, gnome-terminal, xfce4-terminal or xterm.
6. It replies `{status: ok}` and exits. From here the terminal runs on its own, so closing the popup or the browser changes nothing.
7. The script runs yt-dlp (batched for playlists), and in audio mode starts the lyrics worker alongside it, if lyrics are enabled and the packages are installed.
8. At the end it sends a desktop notification, with `notify-send` or else `kdialog`, removes its temp files and deletes itself. The terminal closes on a clean run.

## Batching

Playlists and channels do not run as one yt-dlp process, because the browser cookies are read once per process and went stale partway through long runs.

- **Size lookup.** The host asks yt-dlp for the playlist count (`--flat-playlist --print playlist_count`, 20 second limit). If you asked for the first X items, the total is the smaller of X and the count.
- **Ranges.** The total is cut into ranges of `batch_size` (`1-10`, `11-20`, ...) and each one is passed to yt-dlp as `--playlist-items`.
- **Pause.** A random 2 to 3 second pause sits between batches, not before the first.
- **Unknown size.** If the count lookup fails, the host assumes up to 2000 items (or X, if you set a limit) and marks the size as a guess. A batch that adds no files then ends the loop, since it means the playlist ran out.
- **Known size.** Empty batches do not stop the loop, so a few private or removed items in the middle don't cut the run short.
- **Errors.** After each batch, a non-zero exit code or an `ERROR` line in its stderr marks the whole run as having errors.

Single videos skip all of this and use the format-retry loop instead.

## Config Loading

- `host.py` starts from built-in defaults, then reads `config.ini`, then `config_local.ini` on top. Only the keys present in a later file override.
- A blank value falls back to the default. A number that doesn't parse falls back to its default, and numbers below 1 are raised to 1.
- If a config file is malformed, the host ignores both files and uses the built-in defaults, so a typo can't stop downloads.
- `sync.sh` reads the same two files, for `music_dir` and the `[sync]` section.

## Folder Resolution

The base is `music_dir` for audio and `video_dir` for video. The `where` choice then picks the folder:

| `where` | Folder |
|---|---|
| `flat` | `<base>/<flat_folder>` |
| `auto` | `<base>/` plus a yt-dlp template that expands to the playlist title, else the channel, else the uploader, else `Misc` |
| `custom` | `<base>/<folder>`, with the name cleaned. An empty or dots-only result falls back to `flat`. |

The script only creates a folder up front when the path has no yt-dlp template in it. A template path is left for yt-dlp to create, or a literal folder named after the template would appear.

## Failure Handling

- **What keeps the terminal open:** a non-zero yt-dlp exit or an `ERROR` line in any batch, a lyrics step that fails or can't find its script, a notification that can't be sent, or a run that saved nothing. The window waits for Enter.
- **What does not:** missing lyrics packages (lyrics are skipped with one line), a song with no lyrics found, or a song with missing tags. These are normal outcomes.
- **Format retry (single videos).** If yt-dlp says "Requested format is not available", the script lists the formats and asks for one to retry with. A blank answer gives up and counts as an error.
- **Cache and counter.** A broken run counter never stops a download. It only means no cache wipe that time.

## Lyrics Worker

`add_lyrics.py` runs in the background and follows the list of finished file paths that yt-dlp appends to (`--print-to-file after_move:filepath`). Each song is looked up as soon as it is saved, so lyrics never hold up the next download.

- **Lookup.** It searches the providers in order (Lrclib, Genius, NetEase, AZLyrics) using the cleaned title plus the artist tag.
- **Skips.** Files with no title or artist tag, and files that already have lyrics, are skipped.
- **Output.** Its output goes to a log, not the terminal, so it can't break the in-place progress line. The log is shown once downloads finish.
- **Finish.** The script creates a marker file when the last download ends. The worker stops once the marker exists and the list is used up.

## Phone Sync

`scripts/sync.sh` is separate from the download path. The extension sends `{action: "sync"}`, and `host.py` opens a terminal running the script instead of building a download. The script reads `music_dir` and the `[sync]` section, mounts the phone with `jmtpfs`, runs `rsync` into `phone_dir`, and unmounts. Like a download, it stays open on error and closes on success.

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
