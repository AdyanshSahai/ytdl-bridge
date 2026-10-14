#!/usr/bin/env python3
"""
clean_names.py — strip YouTube junk out of downloaded audio filenames.

Removes things like:
  (Official Video), (Official Lyric Video), (Official Music Video),
  [Official Video], (Lyric Video), (Audio), (Visualizer),
  everything after a "|" (playlist/description spam),
  "[original song]", ".temp" leftovers, duplicate whitespace, etc.

Usage:
  python3 clean_names.py /path/to/folder            # dry run, just prints what would change
  python3 clean_names.py /path/to/folder --apply     # actually renames files

Only touches files with the given extension (default: .opus). Run without
--apply first and check the output before committing to it — a few titles
have odd formatting and might need a manual tweak after.

Renaming also rewrites each renamed file's title tag to the cleaned song
title (always without the "Artist - " prefix, even with --keep-artist), so
the tag doesn't keep saying "Artist - Song (Official 4K Video)". Needs
mutagen (pip install mutagen). Pass --no-tags to only rename.

*.temp<ext> leftovers are never renamed, only deleted via --clean-temp.

NOTE: this is NOT the same rule set as native/host.py. host.py cleans titles
at download time and only strips brackets that contain junk words (official,
video, audio, lyrics, 4k, hd, remaster...), so "Song (Krono Remix)" keeps its
remix tag. This tool strips ALL bracketed text, so the same file would become
"Song". Use it for tidying files that were downloaded some other way, or when
you want the aggressive cleanup.
"""

import argparse
import re
import sys
from pathlib import Path

# Things to strip out entirely (case-insensitive), including the brackets/parens around them
JUNK_PATTERNS = [
    r'\(\s*official\s*(lyric\s*)?(music\s*)?video\s*\)',
    r'\[\s*official\s*(lyric\s*)?(music\s*)?video\s*\]',
    r'\(\s*official\s*audio\s*\)',
    r'\[\s*official\s*audio\s*\]',
    r'\(\s*lyric\s*video\s*\)',
    r'\[\s*lyric\s*video\s*\]',
    r'\(\s*lyrics?\s*\)',
    r'\[\s*lyrics?\s*\]',
    r'\(\s*audio\s*\)',
    r'\[\s*audio\s*\]',
    r'\(\s*visualizer\s*\)',
    r'\[\s*visualizer\s*\]',
    r'\(\s*official\s*\)',
    r'\[\s*official\s*\]',
    r'\[\s*original\s*song\s*\]',
    r'\(\s*original\s*song\s*\)',
    r'【\s*original\s*song\s*】',
    r'\(\s*hd\s*\)',
    r'\[\s*hd\s*\]',
    r'\(\s*4k\s*\)',
    r'\[\s*4k\s*\]',
]

def clean_stem(stem: str, strip_artist: bool = False) -> str:
    name = stem

    # cut everything from the first "|" (ASCII or fullwidth ｜) onward — this is
    # almost always playlist/channel/description spam tacked on by yt-dlp templates
    name = re.split(r'[|｜]', name)[0]

    # strip the junk patterns (case-insensitive)
    for pat in JUNK_PATTERNS:
        name = re.sub(pat, '', name, flags=re.IGNORECASE)

    # drop a lingering ".temp" some partial downloads leave behind
    name = re.sub(r'\.temp$', '', name, flags=re.IGNORECASE)

    # remove ANY remaining bracketed content — e.g. (Krono Remix), (Remastered 2011),
    # [Deluxe Edition], 「Cover」, 【live】 — whatever's left after the specific
    # junk patterns above, on the assumption brackets almost always carry
    # non-title info (remix/version/edition tags) rather than part of the title
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)
    name = re.sub(r'「[^」]*」', '', name)
    name = re.sub(r'【[^】]*】', '', name)

    # collapse multiple spaces, trim stray leading/trailing punctuation & whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.strip(' -_')

    # optionally drop a leading "Artist - " prefix, keeping just the song title
    if strip_artist:
        name = re.sub(r'^.+?\s+-\s+', '', name)

    return name

def set_title_tag(path: Path, title: str):
    """Write the title tag. Returns None on success, or an error string."""
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return "mutagen not installed, tag not updated"
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None:
            return "unsupported format, tag not updated"
        if audio.tags is None:
            audio.add_tags()
        audio["title"] = title
        audio.save()
        return None
    except Exception as e:
        return f"tag not updated ({e})"

def main():
    ap = argparse.ArgumentParser(description="Clean up messy yt-dlp audio filenames")
    ap.add_argument('directory', type=Path, help='Folder containing the audio files')
    ap.add_argument('--ext', default='.opus', help='File extension to target (default: .opus)')
    ap.add_argument('--apply', action='store_true', help='Actually rename files (default is dry-run)')
    ap.add_argument('--keep-artist', action='store_true',
                     help='Keep the leading "Artist - " prefix instead of stripping it (default strips it)')
    ap.add_argument('-r', '--recursive', action='store_true',
                     help='Recurse into subfolders instead of just the top-level directory')
    ap.add_argument('--skip', action='append', default=[],
                     help='Filename (without extension) to leave completely untouched. '
                          'Can be passed multiple times, e.g. --skip "Dude (Looks Like A Lady)" '
                          '--skip "In The End [Official HD Music Video] - Linkin Park"')
    ap.add_argument('--no-tags', action='store_true',
                     help="Only rename files, don't update their title tags")
    ap.add_argument('--clean-temp', action='store_true',
                     help='Delete all *.temp<ext> files found (e.g. *.temp.opus) before doing anything else')
    args = ap.parse_args()

    if not args.directory.is_dir():
        print(f"Not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    if args.clean_temp:
        glob_fn = args.directory.rglob if args.recursive else args.directory.glob
        temp_files = sorted(glob_fn(f'*.temp{args.ext}'))
        if temp_files:
            for tf in temp_files:
                if args.apply:
                    tf.unlink()
                    print(f"[deleted] {tf}")
                else:
                    print(f"[would delete] {tf}")
            print(f"\n{len(temp_files)} temp file(s) {'deleted' if args.apply else 'would be deleted'}.\n")
        else:
            print(f"No *.temp{args.ext} files found.\n")

    glob_fn = args.directory.rglob if args.recursive else args.directory.glob
    temp_suffix = f'.temp{args.ext}'.lower()
    files = [f for f in sorted(glob_fn(f'*{args.ext}'))
             if not f.name.lower().endswith(temp_suffix)]
    if not files:
        print(f"No {args.ext} files found in {args.directory}")
        return

    changed = 0
    skipped_collisions = []
    tag_errors = []
    planned = set()  # targets claimed earlier in this run, so dry runs catch clashes too
    skip_set = set(args.skip)

    for f in files:
        if f.stem in skip_set:
            print(f"[untouched] {f.name}")
            continue

        new_stem = clean_stem(f.stem, strip_artist=not args.keep_artist)
        if not new_stem:
            print(f"[skip] would result in empty name: {f.name}")
            continue

        new_name = new_stem + f.suffix
        if new_name == f.name:
            continue

        target = f.with_name(new_name)
        if (target.exists() and target != f) or target in planned:
            skipped_collisions.append((f.name, new_name))
            continue
        planned.add(target)

        changed += 1
        if args.apply:
            f.rename(target)
            print(f"[renamed] {f.name}  ->  {new_name}")
            if not args.no_tags:
                err = set_title_tag(target, clean_stem(f.stem, strip_artist=True))
                if err:
                    tag_errors.append((new_name, err))
                    print(f"  [tag error] {err}")
        else:
            print(f"[would rename] {f.name}  ->  {new_name}")

    print(f"\n{changed} file(s) {'renamed' if args.apply else 'would be renamed'}.")
    if skipped_collisions:
        print(f"\n{len(skipped_collisions)} skipped due to name collisions (target already exists):")
        for old, new in skipped_collisions:
            print(f"  {old}  ->  {new}")

    if tag_errors:
        print(f"\n{len(tag_errors)} file(s) renamed but title tag not updated:")
        for name, err in tag_errors:
            print(f"  {name}: {err}")

    if not args.apply and changed:
        print("\nThis was a dry run — nothing was actually renamed. Re-run with --apply to commit.")

if __name__ == '__main__':
    main()
