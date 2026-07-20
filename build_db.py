#!/usr/bin/env python3
"""
Dead Archive Radio — Database Builder
Crawls Archive.org metadata for all identifiers and builds db.json

Usage:
  python3 build_db.py                  # Full build
  python3 build_db.py --resume         # Resume interrupted build
  python3 build_db.py --stats          # Show stats on existing db.json

Output: db.json (host alongside index.html)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import ssl
import re
from datetime import datetime

IDENTIFIERS_FILE = 'identifiers.json'
PROGRESS_FILE    = 'build_progress.json'
OUTPUT_FILE      = 'db.json'

AUDIO_EXTENSIONS = {'.mp3', '.ogg', '.flac', '.m4a', '.aac', '.opus', '.wav', '.mp4'}
AUDIO_FORMATS    = {'MP3', 'OGG', 'FLAC', 'M4A', 'AAC', 'OPUS', 'WAV', 'VBR MP3', '128Kbps MP3',
                    '64Kbps MP3', '192Kbps MP3', '256Kbps MP3', '320Kbps MP3', 'Ogg Vorbis',
                    'FLAC', 'Apple Lossless Audio', 'MP4', '96Kbps MP3', '160Kbps MP3'}

REQUEST_DELAY = 0.6   # seconds between requests
TIMEOUT       = 15    # seconds per request

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ─────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def is_audio_file(f):
    name = f.get('name', '').lower()
    fmt  = f.get('format', '')
    ext  = os.path.splitext(name)[1]
    if ext in AUDIO_EXTENSIONS:
        return True
    if fmt in AUDIO_FORMATS:
        return True
    return False

def clean(val, fallback=''):
    """Strip whitespace, return fallback if empty."""
    if not val:
        return fallback
    v = str(val).strip()
    return v if v else fallback

def parse_duration(val):
    """Convert HH:MM:SS or seconds string to integer seconds."""
    if not val:
        return 0
    s = str(val).strip()
    if ':' in s:
        parts = s.split(':')
        try:
            if len(parts) == 3:
                return int(float(parts[0]))*3600 + int(float(parts[1]))*60 + int(float(parts[2]))
            elif len(parts) == 2:
                return int(float(parts[0]))*60 + int(float(parts[1]))
        except:
            return 0
    try:
        return int(float(s))
    except:
        return 0

def parse_year(val):
    """Extract 4-digit year from a date string."""
    if not val:
        return ''
    s = str(val).strip()
    m = re.search(r'\b(19[0-9]{2}|20[0-9]{2})\b', s)
    return m.group(1) if m else ''

def fetch_metadata(identifier):
    """Fetch Archive.org metadata JSON for an identifier."""
    url = f"https://archive.org/metadata/{identifier}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://archive.org/',
        'Accept': 'application/json'
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl_ctx) as r:
            raw = r.read().decode('utf-8', errors='replace')
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        return {'_error': f'HTTP {e.code}'}
    except urllib.error.URLError as e:
        return {'_error': str(e)}
    except json.JSONDecodeError:
        return {'_error': 'JSON parse error'}
    except Exception as e:
        return {'_error': str(e)}

def extract_tracks(identifier, data, station_meta):
    """
    Extract normalized track records from Archive.org metadata response.
    Returns list of track dicts.
    """
    if '_error' in data:
        return []

    item_meta = data.get('metadata', {})
    files     = data.get('files', [])

    # Item-level fallbacks
    item_creator = clean(item_meta.get('creator') or item_meta.get('artist', ''))
    item_title   = clean(item_meta.get('title', identifier))
    item_date    = parse_year(item_meta.get('date', ''))
    item_genre   = clean(item_meta.get('genre', ''))

    # Handle creator as list
    if isinstance(item_meta.get('creator'), list):
        item_creator = ', '.join(item_meta['creator'])

    audio_files = [f for f in files if is_audio_file(f)]

    # Skip items with no audio (bad identifier)
    if not audio_files:
        return []

    tracks = []
    for f in audio_files:
        name = f.get('name', '')
        if not name:
            continue

        # Skip derivative files (they duplicate originals)
        source = f.get('source', 'original')
        if source == 'derivative':
            fmt = f.get('format', '')
            if fmt not in {'MP3', 'VBR MP3', '128Kbps MP3'}:
                continue

        ext = os.path.splitext(name)[1].lower()

        # Per-file metadata, fall back to item-level
        title   = clean(f.get('title', ''))  or os.path.splitext(name)[0].replace('_', ' ').replace('-', ' ').strip()
        artist  = clean(f.get('artist', '')) or item_creator
        album   = clean(f.get('album', ''))  or item_title
        year    = parse_year(f.get('year', '')) or item_date
        genre   = clean(f.get('genre', ''))  or item_genre
        dur     = parse_duration(f.get('length', 0))
        track_n = clean(f.get('track', ''))

        uid = f"{identifier}::{name}"

        tracks.append({
            'uid':          uid,
            'show':         identifier,
            'file':         name,
            'url':          f"https://archive.org/download/{identifier}/{urllib.request.quote(name)}",
            'title':        title,
            'artist':       artist,
            'album':        album,
            'year':         year,
            'genre':        genre,
            'duration':     dur,
            'track_num':    track_n,
            'station':      station_meta['station'],
            'station_name': station_meta['station_name'],
        })

    return tracks

# ─────────────────────────────────────────────
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {'completed': [], 'tracks': []}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def build_index(tracks):
    """Build sorted unique index of artists, genres, years."""
    artists = sorted(set(t['artist'] for t in tracks if t['artist'] and t['artist'] != 'Unknown'))
    genres  = sorted(set(t['genre']  for t in tracks if t['genre']))
    years   = sorted(set(t['year']   for t in tracks if t['year']), reverse=True)
    stations = sorted(set(
        (t['station'], t['station_name']) for t in tracks
    ), key=lambda x: x[0])
    return {
        'artists':  artists[:5000],  # Cap to keep db.json manageable
        'genres':   genres,
        'years':    years,
        'stations': [{'num': s[0], 'name': s[1]} for s in stations]
    }

def write_db(tracks):
    index = build_index(tracks)
    db = {
        'version': 1,
        'built':   datetime.utcnow().isoformat() + 'Z',
        'total_tracks': len(tracks),
        'total_shows':  len(set(t['show'] for t in tracks)),
        'index':   index,
        'tracks':  tracks,
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, separators=(',', ':'))
    size_mb = os.path.getsize(OUTPUT_FILE) / 1_000_000
    log(f"Wrote {OUTPUT_FILE} — {len(tracks):,} tracks, {size_mb:.1f} MB")

# ─────────────────────────────────────────────
def show_stats():
    if not os.path.exists(OUTPUT_FILE):
        print("db.json not found. Run without --stats first.")
        return
    with open(OUTPUT_FILE) as f:
        db = json.load(f)
    print(f"\n{'='*50}")
    print(f"  db.json stats")
    print(f"{'='*50}")
    print(f"  Built:        {db.get('built','?')}")
    print(f"  Total tracks: {db['total_tracks']:,}")
    print(f"  Total shows:  {db['total_shows']:,}")
    print(f"  Artists:      {len(db['index']['artists']):,}")
    print(f"  Genres:       {len(db['index']['genres']):,}")
    print(f"  Years:        {db['index']['years'][:5]}...")
    size_mb = os.path.getsize(OUTPUT_FILE) / 1_000_000
    print(f"  File size:    {size_mb:.1f} MB")
    print(f"{'='*50}\n")

# ─────────────────────────────────────────────
def main():
    if '--stats' in sys.argv:
        show_stats()
        return

    resume = '--resume' in sys.argv

    if not os.path.exists(IDENTIFIERS_FILE):
        print(f"ERROR: {IDENTIFIERS_FILE} not found. Run this script from the same directory.")
        sys.exit(1)

    with open(IDENTIFIERS_FILE) as f:
        identifiers = json.load(f)

    progress = load_progress() if resume else {'completed': [], 'tracks': []}
    completed = set(progress['completed'])
    tracks    = progress['tracks']

    todo = [(id_, meta) for id_, meta in identifiers.items() if id_ not in completed]
    total = len(identifiers)
    done  = len(completed)

    log(f"Dead Archive Radio — Database Builder")
    log(f"Total identifiers: {total} | Already done: {done} | Remaining: {len(todo)}")
    log(f"Estimated time: {len(todo) * REQUEST_DELAY / 60:.0f} min")
    log(f"Output: {OUTPUT_FILE}")
    log("-" * 50)

    errors = 0
    for i, (identifier, station_meta) in enumerate(todo):
        pct = ((done + i + 1) / total) * 100
        log(f"[{pct:5.1f}%] {done+i+1}/{total} — {identifier}")

        data = fetch_metadata(identifier)

        if '_error' in data:
            log(f"  ⚠ Error: {data['_error']}")
            errors += 1
        else:
            new_tracks = extract_tracks(identifier, data, station_meta)
            tracks.extend(new_tracks)
            log(f"  ✓ {len(new_tracks)} audio files")

        completed.add(identifier)
        progress['completed'] = list(completed)
        progress['tracks']    = tracks

        # Save progress every 10 identifiers
        if (i + 1) % 10 == 0:
            save_progress(progress)
            log(f"  → Progress saved ({len(tracks):,} tracks so far)")

        time.sleep(REQUEST_DELAY)

    # Final save
    save_progress(progress)
    write_db(tracks)

    log("=" * 50)
    log(f"Build complete!")
    log(f"  Identifiers processed: {total}")
    log(f"  Tracks extracted:      {len(tracks):,}")
    log(f"  Errors:                {errors}")
    log(f"  Output:                {OUTPUT_FILE}")
    log("=" * 50)
    log("Host db.json alongside index.html and you're live.")

if __name__ == '__main__':
    main()
