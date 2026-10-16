#!/usr/bin/env python3
"""
add_lyrics.py - fetches and embeds lyrics into .opus files under MUSIC_DIR.

Usage:
    python3 add_lyrics.py --music-dir ~/Music           # process everything (minus blacklist)
    python3 add_lyrics.py --whitelist "yt-rips"         # only this folder (and its subfolders)
    python3 add_lyrics.py --whitelist "yt-rips" --whitelist "RHCP"   # multiple, repeatable
    python3 add_lyrics.py --file-list /tmp/list.txt     # only the .opus paths listed (one per line)
    python3 add_lyrics.py --file-list /tmp/list.txt --follow /tmp/done
                                                        # keep watching the list for new lines and
                                                        # process each as it appears; stop once
                                                        # /tmp/done exists and the list is used up
                                                        # (this is what host.py runs during a download)
    python3 add_lyrics.py --whitelist "MJ_top-hits" --title-from-filename
                                                        # first set each title tag to the file name
                                                        # (for files renamed by hand), then fetch lyrics

Folder-scan mode also takes --music-dir (default: $YTDL_MUSIC_DIR, else ~/Music)
and --blacklist NAME (repeatable) to skip folders by name or relative path.

Needs: pip install --user mutagen syncedlyrics

--title-from-filename is off by default on purpose: album rips named like
"01 - Song.opus" would get "01 - Song" as their title.
"""

import argparse
import os
import re
import sys
import time
from mutagen.oggopus import OggOpus
import syncedlyrics

# only used by the folder-scan mode (no --file-list). host.py never needs it.
# set with --music-dir, or the YTDL_MUSIC_DIR environment variable.
MUSIC_DIR = os.path.expanduser(os.environ.get("YTDL_MUSIC_DIR", "~/Music"))

# fastest first: Lrclib is a plain API and answers most songs in about a second
PROVIDERS = ["Lrclib", "Genius", "NetEase", "AZLyrics"]

# Folders to skip entirely in folder-scan mode - match either just the folder
# name (anywhere in the tree, e.g. "Soundtracks") or a path relative to MUSIC_DIR
# (only that location, e.g. "2023_FavSongs/OldStuff"). Still applies inside a
# --whitelist'd folder. Filled from --blacklist (repeatable); empty by default.
BLACKLIST_DIRS = set()

# set when something actually went wrong (unreadable file, provider error,
# failed save). 'not found' and 'missing tags' are normal outcomes, not errors.
had_error = False

def is_blacklisted(dirpath):
    name = os.path.basename(dirpath)
    rel = os.path.relpath(dirpath, MUSIC_DIR)
    return name in BLACKLIST_DIRS or rel in BLACKLIST_DIRS

def search_title(title):
    """Strip "| channel spam" and any bracketed bits from the title before
    searching. The tag itself is left alone, this is only the query."""
    t = re.split(r'[|｜]', title)[0]
    t = re.sub(r'\s*[\(\[【「][^\)\]】」]*[\)\]】」]', '', t)
    t = ' '.join(t.split()).strip(' -_')
    return t or title

def save(audio, f):
    global had_error
    try:
        audio.save()
        return True
    except Exception as e:
        print(f"error saving {f}: {e}")
        had_error = True
        return False

def process_file(path, f, title_from_filename=False):
    global had_error
    try:
        audio = OggOpus(path)
    except Exception as e:
        print(f"skip (unreadable): {f} ({e})")
        had_error = True
        return

    title = audio.get("title", [None])[0]
    artist = audio.get("artist", [None])[0]

    if title_from_filename:
        stem = os.path.splitext(f)[0]
        if stem and title != stem:
            audio["title"] = stem
            if not save(audio, f):
                return
            print(f"retitled: {f} (was: {title})")
            title = stem

    if not title or not artist:
        print(f"skip (missing tags): {f}")
        return

    if "lyrics" in audio:
        print(f"skip (already has lyrics): {f}")
        return

    try:
        lrc = syncedlyrics.search(
              f"{search_title(title)} {artist}",
              providers=PROVIDERS,
        )
    except Exception as e:
        print(f"error on {f}: {e}")
        had_error = True
        return

    if lrc:
        audio["lyrics"] = lrc
        if save(audio, f):
            print(f"added: {f}")
    else:
        print(f"not found: {f}")

    time.sleep(0.5)

def handle_listed(p, tff):
    global had_error
    if not p.endswith(".opus"):
        return
    if os.path.isfile(p):
        process_file(p, os.path.basename(p), tff)
    else:
        print(f"missing: {p}")
        had_error = True

def follow_list(list_path, done_flag, tff):
    """Process lines as they get appended to list_path. Only complete lines
    (ending in a newline) are used, so a half-written path is never read.
    Stops once done_flag exists and everything up to that point is done."""
    pos = 0
    buf = b""
    while True:
        # check the flag *before* reading, so any line written before the
        # flag appeared is guaranteed to be picked up by this last read
        finished = os.path.exists(done_flag)
        with open(list_path, "rb") as fh:
            fh.seek(pos)
            chunk = fh.read()
            pos = fh.tell()
        buf += chunk
        *lines, buf = buf.split(b"\n")
        for raw in lines:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                handle_listed(line, tff)
        if finished:
            tail = buf.decode("utf-8", errors="replace").strip()
            if tail:
                handle_listed(tail, tff)
            return
        time.sleep(1)

def main():
    global had_error
    parser = argparse.ArgumentParser(description="Fetch and embed lyrics into .opus files.")
    parser.add_argument(
        "--whitelist", action="append", default=[],
        help="Only process this folder, relative to MUSIC_DIR (e.g. 'yt-rips'). "
             "Can be passed multiple times. If omitted, everything under MUSIC_DIR "
             "is processed except BLACKLIST_DIRS."
    )
    parser.add_argument(
        "--file-list",
        help="Text file with one file path per line. Only the .opus files listed "
             "are processed (no folder scan). Used by host.py after a download."
    )
    parser.add_argument(
        "--title-from-filename", action="store_true",
        help="Set each file's title tag to its file name (minus .opus) before "
             "searching. Use after renaming files by hand."
    )
    parser.add_argument(
        "--follow", metavar="DONE_FLAG",
        help="With --file-list: keep watching the list and process new lines "
             "as they're added, until DONE_FLAG exists. Used by host.py."
    )
    parser.add_argument(
        "--music-dir",
        help="Root folder for folder-scan mode. Default: $YTDL_MUSIC_DIR, else ~/Music."
    )
    parser.add_argument(
        "--blacklist", action="append", default=[],
        help="Folder to skip in folder-scan mode, by name or path relative to "
             "the music dir. Can be passed multiple times."
    )
    args = parser.parse_args()
    tff = args.title_from_filename

    global MUSIC_DIR
    if args.music_dir:
        MUSIC_DIR = os.path.expanduser(args.music_dir)
    BLACKLIST_DIRS.update(args.blacklist)

    if args.follow and not args.file_list:
        parser.error("--follow needs --file-list")

    if args.file_list:
        if args.follow:
            follow_list(args.file_list, args.follow, tff)
        else:
            with open(args.file_list, encoding="utf-8") as fh:
                for l in fh:
                    if l.strip():
                        handle_listed(l.strip(), tff)
        sys.exit(1 if had_error else 0)

    if args.whitelist:
        walk_roots = []
        for w in args.whitelist:
            full = os.path.join(MUSIC_DIR, w)
            if not os.path.isdir(full):
                print(f"WARNING: --whitelist folder not found, skipping: {w}")
                continue
            walk_roots.append(full)
        if not walk_roots:
            print("No valid --whitelist folders found. Nothing to do.")
            return
    else:
        walk_roots = [MUSIC_DIR]

    for base in walk_roots:
        for root, dirs, files in os.walk(base):
            # prune blacklisted subfolders in place so os.walk never
            # descends into them at all, even within a whitelisted tree
            dirs[:] = [d for d in dirs if not is_blacklisted(os.path.join(root, d))]

            for f in files:
                if not f.endswith(".opus"):
                    continue
                process_file(os.path.join(root, f), f, tff)

    sys.exit(1 if had_error else 0)

if __name__ == "__main__":
    main()
