#!/usr/bin/python3
"""
Native messaging host for ytdl-bridge - Linux version.

Receives { url, mode, where, folder, limit, forceSingle } from the extension.
  mode        = 'audio' -> opus rip via yt-dlp, then lyrics via add_lyrics.py
                 (titles cleaned on the way in: 'Artist - Song (Official Video)'
                  -> title 'Song', artist 'Artist')
  mode        = 'video' -> yt-dlp, mkv output
  where       = 'flat'   -> <base>/<flat_folder>
                'auto'   -> <base>/<playlist or channel name>, using yt-dlp's
                            own %(playlist_title,channel,...) template
                'custom' -> <base>/<folder>
                <base> is music_dir or video_dir from config.ini, so the
                extension never needs to know any paths.
  folder      = the name typed for 'custom' (cleaned here, see clean_folder_name)
  limit       = int or null ("first X items")
  forceSingle = true -> download only the open video, ignore playlist context

Output: yt-dlp runs quiet and prints "Downloading: ..." before and
"Saved: ..." after each item via --print, with a progress line that
rewrites itself in place in between. yt-dlp only does the in-place rewrite
when stdout is a real terminal, so nothing may be piped on the stdout side
(no tee/uniq). The notification shows the song title (first title + N more
for playlists).

Every finished file path is appended to a temp list (--print-to-file). In
audio mode add_lyrics.py runs in the background from the start, following
that list: as soon as a song is saved its lyrics get fetched while the next
song downloads (lyrics never hold up yt-dlp). Its output goes to a log that
is shown once the downloads are done, and the script waits for it to finish
the last few songs. A desktop notification fires at the very end, after
lyrics, and the terminal window closes itself. If anything at all went wrong (yt-dlp
exit code or ERROR line, a failed lyrics step, a failed notification,
nothing saved) the window stays open so it can be read.

Each run keeps its own temp download archive (--download-archive), so a
video that appears twice in one playlist is only downloaded once and the
repeat is skipped silently. The archive is deleted at the end of the run,
so it never stops a later re-download.

Playlists/channels run in batches of BATCH_SIZE so --cookies-from-browser
re-reads fresh cookies, with a random 2-3s pause between batches.

yt-dlp's cache is wiped every CACHE_WIPE_EVERY runs (a run = one message
from the extension, audio or video). The count lives in RUN_COUNT_FILE. Single downloads get a format-retry loop: on
"Requested format is not available" the terminal lists formats and lets
you paste one to retry with.
"""

import sys
import json
import struct
import subprocess
import shutil
import tempfile
import os
import re
import shlex
import configparser

CHANNEL_RE = re.compile(r'/(@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+)/(videos|streams|shorts)?')

# every user-facing setting lives in config.ini (defaults) and config_local.ini
# (personal overrides, gitignored) at the repo root. The values below are only
# the fallback if a key is missing or can't be parsed.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DEFAULTS = {
    'folders': {'music_dir': '~/Music', 'video_dir': '~/Videos', 'flat_folder': 'yt-rips'},
    'browser': {'cookies_from': 'brave'},
    'download': {'audio_format': 'bestaudio[abr=128]/bestaudio',
                 'video_format': 'bestvideo+bestaudio/best',
                 'batch_size': '10', 'cache_wipe_every': '10'},
    'lyrics': {'enabled': 'true'},
}


def load_config():
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_dict(CONFIG_DEFAULTS)
    try:
        cp.read([os.path.join(ROOT_DIR, 'config.ini'),
                 os.path.join(ROOT_DIR, 'config_local.ini')], encoding='utf-8')
    except configparser.Error:
        # a malformed file shouldn't stop downloads: start again from defaults
        cp = configparser.ConfigParser(interpolation=None)
        cp.read_dict(CONFIG_DEFAULTS)
    return cp


CFG = load_config()


def cfg_str(section, key):
    return CFG.get(section, key).strip() or CONFIG_DEFAULTS[section][key]


def cfg_int(section, key):
    try:
        return max(1, int(cfg_str(section, key)))
    except ValueError:
        return int(CONFIG_DEFAULTS[section][key])


MUSIC_DIR = os.path.expanduser(cfg_str('folders', 'music_dir'))
VIDEO_DIR = os.path.expanduser(cfg_str('folders', 'video_dir'))
FLAT_FOLDER = cfg_str('folders', 'flat_folder')
COOKIES_FROM = cfg_str('browser', 'cookies_from')
DEFAULT_AUDIO_FMT = cfg_str('download', 'audio_format')
DEFAULT_VIDEO_FMT = cfg_str('download', 'video_format')
BATCH_SIZE = cfg_int('download', 'batch_size')
CACHE_WIPE_EVERY = cfg_int('download', 'cache_wipe_every')
LYRICS_ENABLED = cfg_str('lyrics', 'enabled').lower() in ('1', 'true', 'yes', 'on')

DEFAULT_TOTAL = 2000  # fallback upper bound if get_playlist_count() fails

SYNC_SCRIPT = os.path.join(ROOT_DIR, 'scripts', 'sync.sh')

LYRICS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'add_lyrics.py')

RUN_COUNT_FILE = os.path.expanduser('~/.local/state/ytdl-host/run_count')


def cookie_args():
    """--cookies-from-browser <x>, or nothing if cookies_from = none."""
    if COOKIES_FROM.lower() == 'none':
        return []
    return ['--cookies-from-browser', COOKIES_FROM]


START_TEMPLATE = 'before_dl:[%(playlist_index|-)s/%(playlist_count|-)s] Downloading: %(title|Unknown).60s'
DONE_TEMPLATE = 'after_move:[%(playlist_index|-)s/%(playlist_count|-)s] Saved: %(title|Unknown).60s'
PROGRESS_TEMPLATE = 'download:    %(progress._percent_str)s  %(progress._speed_str)s  eta %(progress._eta_str)s'

COMMON_ARGS = [
    '--embed-metadata', '--embed-thumbnail', '--convert-thumbnails', 'jpg',
    '--concurrent-fragments', '16',
    '--ignore-errors', '--quiet', '--no-warnings',
    '--progress', '--progress-delta', '0.3',
    '--progress-template', PROGRESS_TEMPLATE,
    '--print', START_TEMPLATE,
    '--print', DONE_TEMPLATE,
    '--postprocessor-args', 'ffmpeg:-loglevel quiet -hide_banner',
]
# youtube titles are usually "Artist - Song (Official 4K Video)". split off the
# artist, then strip bracketed junk. runs before the filename is built, so the
# file name, title tag and artist tag all come out clean. titles without
# " - " just skip the split (the failure is hidden by --no-warnings).
TITLE_JUNK_RE = (r'(?i)\s*[\(\[][^\)\]]*\b(?:official|video|audio|lyrics?|'
                 r'visuali[sz]er|4k|hd|hq|mv|m/v|remaster(?:ed)?)\b[^\)\]]*[\)\]]')
AUDIO_ARGS = [
    '-x', '--audio-format', 'opus', '--audio-quality', '128',
    '--parse-metadata', r'title:^(?P<artist>.+?) - (?P<title>.+)$',
    '--replace-in-metadata', 'title', TITLE_JUNK_RE, '',
]
VIDEO_ARGS = [
    '--write-subs', '--no-write-auto-subs', '--embed-subs', '--sub-langs', 'en',
    '--merge-output-format', 'mkv', '--remote-components', 'ejs:github',
]

SCRIPT_TEMPLATE = r'''#!/bin/bash
FMT=@@FMT@@
TARGET=@@TARGET@@
URL=@@URL@@
LYRICS=@@LYRICS@@
HAD_ERROR=0
LIST=$(mktemp /tmp/ytdl_list_XXXXXX)
TITLES=$(mktemp /tmp/ytdl_titles_XXXXXX)
LYRLOG=$(mktemp /tmp/ytdl_lyrlog_XXXXXX)
ARCHIVE=$(mktemp /tmp/ytdl_archive_XXXXXX)      # per-run, skips repeats in a playlist
LYRDONE=$(mktemp -u /tmp/ytdl_lyrdone_XXXXXX)   # created when downloads finish
LYR_PID=

# only pre-create real folders. A path containing a yt-dlp template
# (%(...)s) must be left alone or it becomes a literal junk folder.
case "$TARGET" in
  *'%('*) ;;
  *) mkdir -p "$TARGET" ;;
esac

run_dl() {
  local ITEM_ARGS=()
  [ -n "$1" ] && ITEM_ARGS=(--playlist-items "$1")
  yt-dlp @@ARGS@@ --download-archive "$ARCHIVE" --print-to-file 'after_move:filepath' "$LIST" --print-to-file 'after_move:%(title)s' "$TITLES" -f "$FMT" "${ITEM_ARGS[@]}" -o "$TARGET/%(title)s.%(ext)s" "$URL"
}

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -a "ytdl-bridge" -- "$1" "$2" || { echo "notify-send failed (exit $?), no desktop notification sent"; HAD_ERROR=1; }
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --title "ytdl-bridge" --passivepopup "$1: $2" 8 || { echo "kdialog failed, no desktop notification sent"; HAD_ERROR=1; }
  else
    echo "no notify-send or kdialog found, no desktop notification sent"
    HAD_ERROR=1
  fi
}

@@CACHE_WIPE@@

echo "Starting @@MODE@@ download..."

@@LYRICS_START@@

@@BODY@@

@@LYRICS_FINISH@@

COUNT=$(wc -l < "$LIST")
if [ "$COUNT" -gt 0 ]; then
  FIRST=$(head -n1 "$TITLES")
  if [ "$COUNT" -eq 1 ]; then BODY="$FIRST"; else BODY="$FIRST + $((COUNT - 1)) more"; fi
  if [ "$HAD_ERROR" -ne 0 ]; then
    notify "Download finished with errors" "$BODY"
  else
    notify "Download finished" "$BODY"
  fi
else
  HAD_ERROR=1
  notify "Download failed" "Nothing saved, check the terminal (${URL:0:60})"
fi

rm -f "$LIST" "$TITLES" "$LYRLOG" "$LYRDONE" "$ARCHIVE"
rm -f -- "$0"

# clean run: the window just closes (the notification says it's done).
# any error at all: stay open so it can be read.
if [ "$HAD_ERROR" -ne 0 ]; then
  echo
  echo "Finished with errors (see above). Press enter to close."
  read -r
fi
'''

MULTI_BODY = r'''KNOWN=@@KNOWN@@   # 1 = real playlist size known, 0 = guessing
FIRST_BATCH=1
for R in @@RANGES@@; do
  # random 2.00-2.99s pause between batches, skipped before the first
  [ "$FIRST_BATCH" -eq 0 ] && sleep "$(printf '2.%02d' $((RANDOM % 100)))"
  FIRST_BATCH=0
  BEFORE=$(wc -l < "$LIST")
  ERRF=$(mktemp)
  run_dl "$R" 2> "$ERRF"
  RC=$?
  cat "$ERRF" >&2
  AFTER=$(wc -l < "$LIST")
  if [ "$KNOWN" -eq 0 ] && [ "$AFTER" -eq "$BEFORE" ]; then
    rm -f "$ERRF"
    break   # size was a guess and this batch added nothing: end of playlist
  fi
  if [ "$RC" -ne 0 ] || grep -q '^ERROR' "$ERRF"; then HAD_ERROR=1; fi
  rm -f "$ERRF"
done'''

RETRY_BODY = r'''while true; do
  OUT=$(mktemp)
  # stdout stays on the terminal so the progress line can update in place;
  # only stderr goes to a file so the format error can be detected
  run_dl "" 2> "$OUT"
  RC=$?
  cat "$OUT" >&2
  if grep -q "Requested format is not available" "$OUT"; then
    rm -f "$OUT"
    echo
    echo -e "\033[1;33mFormat '$FMT' unavailable. Listing available formats...\033[0m"
    yt-dlp @@COOKIES@@ -F "$URL"
    echo
    read -r -p "Paste the format code/string to retry with (blank to give up): " NEWFMT
    if [ -z "$NEWFMT" ]; then
      echo -e "\033[0;90mGiving up on this download.\033[0m"
      HAD_ERROR=1
      break
    fi
    FMT="$NEWFMT"
    continue
  fi
  if [ "$RC" -ne 0 ] || grep -q '^ERROR' "$OUT"; then HAD_ERROR=1; fi
  rm -f "$OUT"
  break
done'''

# background lyrics worker: follows $LIST as yt-dlp appends to it. Output
# goes to a log instead of the terminal so it can't mangle the in-place
# progress line; the log is shown once downloads are done.
LYRICS_START = r'''if [ ! -f "$LYRICS" ]; then
  echo "add_lyrics.py not found at $LYRICS, skipping lyrics"
  HAD_ERROR=1
elif ! python3 -c 'import mutagen, syncedlyrics' 2>/dev/null; then
  # lyrics are an optional extra: missing packages just skip them
  echo "lyrics skipped (pip install --user mutagen syncedlyrics to enable)"
else
  python3 -u "$LYRICS" --file-list "$LIST" --follow "$LYRDONE" > "$LYRLOG" 2>&1 &
  LYR_PID=$!
fi'''

LYRICS_FINISH = r'''if [ -n "$LYR_PID" ]; then
  touch "$LYRDONE"   # tells the worker no more songs are coming
  echo
  echo "Lyrics:"
  tail -n +1 -f --pid="$LYR_PID" "$LYRLOG"
  wait "$LYR_PID" || { echo "lyrics step reported errors (exit $?)"; HAD_ERROR=1; }
fi'''

CACHE_WIPE = r'''echo "Run #@@RUN_NO@@: wiping yt-dlp cache (every @@EVERY@@ runs)..."
yt-dlp --rm-cache-dir >/dev/null 2>&1 || echo "cache wipe failed, carrying on"'''


def read_message():
    raw = sys.stdin.buffer.read(4)
    if not raw:
        sys.exit(0)
    length = struct.unpack('=I', raw)[0]
    return json.loads(sys.stdin.buffer.read(length).decode('utf-8'))


def send_message(data):
    encoded = json.dumps(data).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('=I', len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def next_run_number():
    """Bump and return the persistent run counter (1, 2, 3, ...). Never
    raises: a broken counter just means no cache wipe this time."""
    try:
        with open(RUN_COUNT_FILE) as f:
            n = int(f.read().strip()) + 1
    except Exception:
        n = 1
    try:
        os.makedirs(os.path.dirname(RUN_COUNT_FILE), exist_ok=True)
        with open(RUN_COUNT_FILE, 'w') as f:
            f.write(str(n))
    except Exception:
        return 0
    return n


def get_playlist_count(url):
    """Ask yt-dlp for the real number of items so we don't build hundreds
    of pointless empty batches when the actual playlist is small."""
    try:
        result = subprocess.run(
            ['yt-dlp', '--flat-playlist', '--print', 'playlist_count', url],
            capture_output=True, text=True, timeout=20
        )
        digits = [l for l in result.stdout.strip().splitlines() if l.strip().isdigit()]
        if digits:
            return int(digits[0])
    except Exception:
        pass
    return None


def clean_folder_name(name):
    """The 'custom' folder name, made safe to use as one path segment.
    Quotes, backticks, $, backslashes and / are stripped (so it can't climb
    out of the base folder or break the shell), and % is stripped because
    yt-dlp would read it as an output template. A name that is empty or only
    dots ('..') is rejected, which is what stops path traversal."""
    name = re.sub(r'["\'`$\\/%]', '', name or '').strip()
    if not name or set(name) <= {'.'}:
        return ''
    return name


def resolve_target(mode, where, folder):
    """Turn the popup's choice into a real folder (or a yt-dlp output
    template, for 'auto') under the music/video base from config.ini."""
    base = MUSIC_DIR if mode == 'audio' else VIDEO_DIR
    if where == 'auto':
        return f'{base}/%(playlist_title,channel,uploader|Misc)s'
    if where == 'custom':
        name = clean_folder_name(folder)
        if name:
            return f'{base}/{name}'
    return f'{base}/{FLAT_FOLDER}'


def batch_ranges(total):
    ranges, start = [], 1
    while start <= total:
        end = min(start + BATCH_SIZE - 1, total)
        ranges.append(f'{start}-{end}')
        start = end + 1
    return ranges


def build_script(url, mode, target, is_multi, limit=None, run_no=0):
    audio = (mode == 'audio')
    if run_no and run_no % CACHE_WIPE_EVERY == 0:
        cache_wipe = (CACHE_WIPE.replace('@@RUN_NO@@', str(run_no))
                                .replace('@@EVERY@@', str(CACHE_WIPE_EVERY)))
    else:
        cache_wipe = ':'

    args = COMMON_ARGS + cookie_args() + (AUDIO_ARGS if audio else VIDEO_ARGS)
    if not is_multi:
        args = args + ['--no-playlist']  # forceSingle on a watch?v=..&list=.. url

    if is_multi:
        count = get_playlist_count(url)  # None if yt-dlp couldn't tell us
        if limit and count:
            total, known = min(int(limit), count), True
        elif limit:
            total, known = int(limit), False
        elif count:
            total, known = count, True
        else:
            total, known = DEFAULT_TOTAL, False
        body = (MULTI_BODY
                .replace('@@KNOWN@@', '1' if known else '0')
                .replace('@@RANGES@@', ' '.join(batch_ranges(total))))
    else:
        body = RETRY_BODY

    script = SCRIPT_TEMPLATE
    for token, value in {
        '@@FMT@@': shlex.quote(DEFAULT_AUDIO_FMT if audio else DEFAULT_VIDEO_FMT),
        '@@TARGET@@': shlex.quote(target),
        '@@URL@@': shlex.quote(url),
        '@@LYRICS@@': shlex.quote(LYRICS_SCRIPT),
        '@@ARGS@@': shlex.join(args),
        '@@MODE@@': mode,
        '@@CACHE_WIPE@@': cache_wipe,
        '@@LYRICS_START@@': LYRICS_START if (audio and LYRICS_ENABLED) else ':',
        '@@BODY@@': body,
        '@@LYRICS_FINISH@@': LYRICS_FINISH if (audio and LYRICS_ENABLED) else ':',
        '@@COOKIES@@': shlex.join(cookie_args()),  # last: it sits inside @@BODY@@
    }.items():
        script = script.replace(token, value)
    return script


def launch_terminal(script_path):
    """Run a bash script in the first terminal emulator found."""
    terminals = [
        ['konsole', '-e', 'bash', script_path],
        ['gnome-terminal', '--', 'bash', script_path],
        ['xfce4-terminal', '-e', f'bash {script_path}'],
        ['xterm', '-e', f'bash {script_path}'],
    ]
    for term in terminals:
        if shutil.which(term[0]):
            subprocess.Popen(term)
            return True
    return False


def main():
    try:
        msg = read_message()
        if msg.get('action') == 'sync':
            if not os.path.isfile(SYNC_SCRIPT):
                send_message({'status': 'error', 'message': 'scripts/sync.sh not found'})
            elif launch_terminal(SYNC_SCRIPT):
                send_message({'status': 'ok', 'action': 'sync'})
            else:
                send_message({'status': 'error', 'message': 'No terminal emulator found'})
            sys.exit(0)
        url = msg.get('url', '')
        mode = msg.get('mode', 'video')
        where = msg.get('where', 'flat')
        folder = msg.get('folder', '')
        limit = msg.get('limit', None)
        force_single = msg.get('forceSingle', False)

        if not url:
            send_message({'status': 'error', 'message': 'No URL'})
            sys.exit(0)

        is_multi = (not force_single) and (
            ('&list=' in url) or ('?list=' in url) or bool(CHANNEL_RE.search(url))
        )

        target = resolve_target(mode, where, folder)

        script = build_script(url, mode, target, is_multi, limit, next_run_number())

        script_fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='ytdl_')
        with os.fdopen(script_fd, 'w') as f:
            f.write(script)
        os.chmod(script_path, 0o755)

        launched = launch_terminal(script_path)

        if launched:
            send_message({'status': 'ok', 'mode': mode, 'url': url, 'dest': target})
        else:
            send_message({'status': 'error', 'message': 'No terminal emulator found'})

    except Exception as e:
        send_message({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    main()
