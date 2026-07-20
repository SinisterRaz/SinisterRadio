#!/usr/bin/env python3
"""
Dead Archive Radio — Content Discovery Tool
Searches Archive.org for new mixtapes/albums matching your station genres,
tests them, and outputs an interactive HTML review page.

Usage:
  python3 discover.py              # Full run
  python3 discover.py --resume     # Resume interrupted run
  python3 discover.py --genre hiphop
  python3 discover.py --limit 50
"""

import json, os, sys, time, ssl, urllib.request, urllib.parse
from datetime import datetime

IDENTIFIERS_FILE = 'identifiers.json'
PROGRESS_FILE    = 'discover_progress.json'
OUTPUT_HTML      = 'discovered.html'
REQUEST_DELAY    = 0.5
TIMEOUT          = 12
MIN_AUDIO_FILES  = 3
MAX_PER_GENRE    = 100
TEST_AUDIO       = True

AUDIO_EXTS = {'.mp3','.ogg','.flac','.m4a','.aac','.opus','.wav'}

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://archive.org/'
}

GENRE_CONFIG = [
    {
        'key': 'hiphop', 'label': '🎤 Hip Hop / Rap', 'stations': [1,2,3,4,5,6,7],
        'queries': [
            'subject:"hip hop" AND subject:"mixtape" AND mediatype:audio',
            'subject:"rap" AND subject:"mixtape" AND mediatype:audio',
            'subject:"hip hop" AND subject:"album" AND mediatype:audio',
            'creator:"DJ" AND subject:"hip hop" AND mediatype:audio',
        ]
    },
    {
        'key': 'reggaeton', 'label': '🔥 Reggaeton / Latin / Dancehall', 'stations': [8,9,10,11,12,13,14],
        'queries': [
            'subject:"reggaeton" AND mediatype:audio',
            'subject:"latin hip hop" AND mediatype:audio',
            'subject:"dancehall" AND mediatype:audio',
        ]
    },
    {
        'key': 'rock', 'label': '🎸 Rock / Metal', 'stations': [18,19,20,21,22,23],
        'queries': [
            'subject:"classic rock" AND subject:"album" AND mediatype:audio',
            'subject:"hard rock" AND mediatype:audio',
            'subject:"heavy metal" AND mediatype:audio',
            'subject:"punk rock" AND mediatype:audio',
        ]
    },
    {
        'key': 'funk', 'label': '🕺 Funk / Soul / 80s', 'stations': [24,25,26,27,28],
        'queries': [
            'subject:"funk" AND subject:"album" AND mediatype:audio',
            'subject:"soul" AND subject:"album" AND mediatype:audio',
            'subject:"r&b" AND subject:"album" AND mediatype:audio',
            'subject:"disco" AND mediatype:audio',
        ]
    },
    {
        'key': 'electronic', 'label': '🎛️ Electronic / Dance / Trance', 'stations': [29,30,31,32,33],
        'queries': [
            'subject:"electronic" AND subject:"album" AND mediatype:audio',
            'subject:"trance" AND mediatype:audio',
            'subject:"house music" AND mediatype:audio',
            'subject:"techno" AND mediatype:audio',
        ]
    },
    {
        'key': 'dnb', 'label': '🥁 Drum & Bass', 'stations': [34,35,36],
        'queries': [
            'subject:"drum and bass" AND mediatype:audio',
            'subject:"drum & bass" AND mediatype:audio',
            'subject:"jungle" AND subject:"music" AND mediatype:audio',
        ]
    },
    {
        'key': 'dubstep', 'label': '🔊 Dubstep / Hardcore', 'stations': [37,38,39,40,41],
        'queries': [
            'subject:"dubstep" AND mediatype:audio',
            'subject:"bass music" AND mediatype:audio',
        ]
    },
    {
        'key': 'ambient', 'label': '🌌 Ambient / Chill', 'stations': [44,45,46,47,48],
        'queries': [
            'subject:"ambient" AND subject:"album" AND mediatype:audio',
            'subject:"chillout" AND mediatype:audio',
            'subject:"lo-fi" AND mediatype:audio',
        ]
    },
    {
        'key': 'jazz', 'label': '🎷 Jazz', 'stations': [59,60],
        'queries': [
            'subject:"jazz" AND subject:"album" AND mediatype:audio',
            'subject:"bebop" AND mediatype:audio',
            'subject:"jazz fusion" AND mediatype:audio',
        ]
    },
    {
        'key': 'country', 'label': '🤠 Country / Americana', 'stations': [42,43],
        'queries': [
            'subject:"country music" AND subject:"album" AND mediatype:audio',
            'subject:"americana" AND mediatype:audio',
            'subject:"bluegrass" AND mediatype:audio',
        ]
    },
    {
        'key': 'reggae', 'label': '🌴 Reggae / Caribbean', 'stations': [16,17],
        'queries': [
            'subject:"reggae" AND mediatype:audio',
            'subject:"roots reggae" AND mediatype:audio',
            'subject:"ska" AND mediatype:audio',
        ]
    },
    {
        'key': 'classicrock', 'label': '🚗 Classic Rock / 70s', 'stations': [70,71,72,73],
        'queries': [
            'subject:"classic rock" AND subject:"album" AND mediatype:audio',
            'subject:"70s rock" AND mediatype:audio',
            'subject:"progressive rock" AND mediatype:audio',
            'subject:"psychedelic rock" AND mediatype:audio',
        ]
    },
    {
        'key': 'world', 'label': '🌍 World / African / Brazilian', 'stations': [62,63,64,65,66,67,68,69],
        'queries': [
            'subject:"afrobeat" AND mediatype:audio',
            'subject:"world music" AND mediatype:audio',
            'subject:"bossa nova" AND mediatype:audio',
            'subject:"afropop" AND mediatype:audio',
        ]
    },
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl_ctx) as r:
            return json.loads(r.read().decode('utf-8', errors='replace'))
    except Exception as e:
        return {'_error': str(e)}

def search_archive(query, rows=MAX_PER_GENRE):
    params = urllib.parse.urlencode({
        'q': query,
        'fl': 'identifier,title,creator,subject,date,downloads',
        'rows': rows, 'output': 'json', 'sort': 'downloads desc',
    })
    data = fetch(f'https://archive.org/advancedsearch.php?{params}')
    if '_error' in data:
        log(f"  Search error: {data['_error']}")
        return []
    return data.get('response', {}).get('docs', [])

def get_audio_files(identifier):
    data = fetch(f'https://archive.org/metadata/{identifier}')
    if '_error' in data:
        return []
    audio = []
    for f in data.get('files', []):
        name = f.get('name', '')
        ext  = os.path.splitext(name)[1].lower()
        fmt  = f.get('format', '')
        src  = f.get('source', 'original')
        if ext in AUDIO_EXTS or fmt in {'MP3','OGG','FLAC','VBR MP3','128Kbps MP3','Ogg Vorbis'}:
            if src != 'derivative' or fmt in {'MP3','VBR MP3','128Kbps MP3'}:
                audio.append({
                    'name': name,
                    'url': f'https://archive.org/download/{identifier}/{urllib.parse.quote(name)}',
                    'title': f.get('title',''),
                    'artist': f.get('artist',''),
                })
    return audio

def test_accessible(url):
    try:
        req = urllib.request.Request(url, method='HEAD', headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=ssl_ctx) as r:
            return r.status == 200
    except:
        return False

# ── HTML Generator ────────────────────────────────────────────────────────────
def write_html(results):
    total = sum(len(d.get('items',[])) for d in results.values())

    genre_sections = ''
    for key, data in results.items():
        items = data.get('items', [])
        if not items:
            continue

        rows = ''
        for item in items:
            subj = ', '.join(item.get('subject', [])[:3])
            rows += f'''
        <tr data-genre="{key}" data-id="{item['identifier']}">
          <td><input type="checkbox" class="item-check" data-id="{item['identifier']}" data-stations="{','.join(str(s) for s in item['stations'])}"></td>
          <td class="title-cell">
            <div class="item-title">{item['title'][:70]}</div>
            <div class="item-sub">{item.get('creator','')}</div>
          </td>
          <td><span class="badge">{item['audio_count']} tracks</span></td>
          <td>{item.get('date','—')}</td>
          <td>{int(item.get('downloads',0)):,}</td>
          <td><div class="subject-tags">{subj}</div></td>
          <td>
            <button class="btn-play" onclick="playSample('{item['sample_url']}',this)" title="Preview">▶</button>
            <a class="btn-archive" href="https://archive.org/details/{item['identifier']}" target="_blank" title="View on Archive.org">🔗</a>
          </td>
        </tr>'''

        genre_sections += f'''
    <section class="genre-section" id="genre-{key}">
      <div class="genre-header">
        <div class="genre-title">{data['genre']}</div>
        <div class="genre-meta">Stations: {', '.join(str(s) for s in data['stations'])} &nbsp;·&nbsp; {len(items)} found</div>
        <div class="genre-actions">
          <button class="btn-sel-all" onclick="selectAll('{key}')">SELECT ALL</button>
          <button class="btn-sel-none" onclick="selectNone('{key}')">NONE</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th style="width:32px"></th>
            <th>Title / Creator</th>
            <th>Tracks</th>
            <th>Year</th>
            <th>Downloads</th>
            <th>Tags</th>
            <th>Actions</th>
          </tr></thead>
          <tbody>{rows}
          </tbody>
        </table>
      </div>
    </section>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dead Archive Radio — Content Discovery</title>
<style>
  :root {{
    --bg: #080810; --frame: #0f0f1a; --border: #1e1e3a;
    --accent: #00ffcc; --accent2: #ff00aa; --text: #e0e0ff;
    --sub: #8888aa; --badge: #1a1a2e; --row-hover: #0f0f20;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; font-size: 14px; }}

  header {{
    background: var(--frame);
    border-bottom: 2px solid var(--accent);
    padding: 20px 24px;
    position: sticky; top: 0; z-index: 100;
    display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
    box-shadow: 0 4px 30px rgba(0,255,200,0.1);
  }}
  .header-title {{ font-size: 20px; font-weight: 700; letter-spacing: 2px; color: var(--accent); }}
  .header-sub {{ color: var(--sub); font-size: 12px; }}
  .header-stats {{ margin-left: auto; display: flex; gap: 20px; }}
  .stat {{ text-align: center; }}
  .stat-num {{ font-size: 22px; font-weight: 700; color: var(--accent); }}
  .stat-label {{ font-size: 10px; color: var(--sub); letter-spacing: 1px; }}

  .toolbar {{
    background: var(--frame);
    border-bottom: 1px solid var(--border);
    padding: 10px 24px;
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  }}
  .toolbar-label {{ color: var(--sub); font-size: 12px; font-weight: 600; letter-spacing: 1px; margin-right: 4px; }}
  .filter-chip {{
    background: var(--badge); border: 1px solid var(--border);
    color: var(--sub); font-size: 12px; font-weight: 600;
    padding: 4px 14px; cursor: pointer; letter-spacing: 1px; transition: all 0.2s;
  }}
  .filter-chip:hover, .filter-chip.active {{
    border-color: var(--accent); color: var(--accent);
  }}
  .btn-generate {{
    margin-left: auto; background: var(--accent); color: #000;
    border: none; font-size: 13px; font-weight: 700; letter-spacing: 2px;
    padding: 8px 24px; cursor: pointer; transition: all 0.2s;
  }}
  .btn-generate:hover {{ background: #00ffee; box-shadow: 0 0 20px rgba(0,255,200,0.5); }}

  main {{ padding: 20px 24px; display: flex; flex-direction: column; gap: 20px; }}

  .genre-section {{ background: var(--frame); border: 1px solid var(--border); }}
  .genre-section.hidden {{ display: none; }}

  .genre-header {{
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
    background: rgba(0,255,200,0.03);
  }}
  .genre-title {{ font-size: 15px; font-weight: 700; letter-spacing: 1px; color: var(--accent); }}
  .genre-meta {{ color: var(--sub); font-size: 12px; }}
  .genre-actions {{ margin-left: auto; display: flex; gap: 6px; }}
  .btn-sel-all, .btn-sel-none {{
    background: transparent; border: 1px solid var(--border);
    color: var(--sub); font-size: 11px; font-weight: 700; letter-spacing: 1px;
    padding: 3px 10px; cursor: pointer; transition: all 0.2s;
  }}
  .btn-sel-all:hover {{ border-color: var(--accent); color: var(--accent); }}
  .btn-sel-none:hover {{ border-color: var(--accent2); color: var(--accent2); }}

  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead tr {{ background: rgba(0,0,0,0.3); }}
  th {{
    text-align: left; padding: 8px 10px;
    font-size: 11px; font-weight: 700; letter-spacing: 1px;
    color: var(--sub); border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }}
  td {{ padding: 8px 10px; border-bottom: 1px solid rgba(30,30,58,0.5); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: var(--row-hover); }}
  tr.selected td {{ background: rgba(0,255,200,0.05); }}

  input[type="checkbox"] {{
    width: 16px; height: 16px; cursor: pointer; accent-color: var(--accent);
  }}

  .item-title {{ font-weight: 600; color: var(--text); font-size: 13px; }}
  .item-sub {{ color: var(--sub); font-size: 11px; margin-top: 2px; }}
  .badge {{
    background: var(--badge); border: 1px solid var(--border);
    color: var(--accent); font-size: 11px; font-weight: 700;
    padding: 2px 8px; white-space: nowrap;
  }}
  .subject-tags {{ color: var(--sub); font-size: 11px; max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  .btn-play {{
    background: transparent; border: 1px solid var(--border);
    color: var(--accent); font-size: 13px; width: 28px; height: 28px;
    cursor: pointer; transition: all 0.15s; display: inline-flex;
    align-items: center; justify-content: center;
  }}
  .btn-play:hover, .btn-play.playing {{
    background: var(--accent); color: #000;
    box-shadow: 0 0 10px rgba(0,255,200,0.5);
  }}
  .btn-archive {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; text-decoration: none; font-size: 13px;
    border: 1px solid var(--border); color: var(--sub); transition: all 0.15s;
  }}
  .btn-archive:hover {{ border-color: var(--accent2); color: var(--accent2); }}

  /* Output modal */
  .modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 999; align-items: center; justify-content: center; padding: 20px; }}
  .modal.open {{ display: flex; }}
  .modal-box {{ background: var(--frame); border: 2px solid var(--accent); width: 100%; max-width: 760px; max-height: 85vh; display: flex; flex-direction: column; }}
  .modal-header {{
    padding: 14px 20px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 12px;
  }}
  .modal-title {{ font-size: 15px; font-weight: 700; letter-spacing: 2px; color: var(--accent); flex: 1; }}
  .btn-close {{ background: transparent; border: 1px solid var(--border); color: var(--sub); font-size: 16px; width: 32px; height: 32px; cursor: pointer; }}
  .btn-close:hover {{ border-color: var(--accent2); color: var(--accent2); }}
  .modal-tabs {{ display: flex; border-bottom: 1px solid var(--border); }}
  .mtab {{ background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--sub); font-size: 12px; font-weight: 700; letter-spacing: 1px; padding: 10px 18px; cursor: pointer; margin-bottom: -1px; }}
  .mtab.active {{ border-bottom-color: var(--accent); color: var(--accent); }}
  .modal-body {{ flex: 1; overflow: auto; padding: 16px; }}
  textarea {{
    width: 100%; height: 100%; min-height: 320px; background: #050508;
    border: 1px solid var(--border); color: #aaffcc;
    font-family: 'Consolas','Courier New',monospace; font-size: 12px;
    padding: 12px; resize: none; outline: none; line-height: 1.6;
  }}
  .modal-footer {{ padding: 12px 20px; border-top: 1px solid var(--border); display: flex; gap: 10px; }}
  .btn-copy {{
    background: var(--accent); color: #000; border: none;
    font-size: 12px; font-weight: 700; letter-spacing: 2px;
    padding: 8px 20px; cursor: pointer;
  }}
  .btn-copy:hover {{ background: #00ffee; }}
  .selection-count {{ color: var(--sub); font-size: 12px; margin-left: auto; align-self: center; }}

  /* Audio player */
  #audio-player {{ display: none; }}

  .no-results {{ color: var(--sub); text-align: center; padding: 40px; font-size: 13px; }}

  @media (max-width: 600px) {{
    header, .toolbar, main {{ padding-left: 12px; padding-right: 12px; }}
    .header-stats {{ display: none; }}
  }}
</style>
</head>
<body>

<audio id="audio-player"></audio>

<header>
  <div>
    <div class="header-title">📡 DEAD ARCHIVE RADIO</div>
    <div class="header-sub">Content Discovery Results — {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
  </div>
  <div class="header-stats">
    <div class="stat"><div class="stat-num" id="total-count">{total}</div><div class="stat-label">ITEMS FOUND</div></div>
    <div class="stat"><div class="stat-num" id="sel-count">0</div><div class="stat-label">SELECTED</div></div>
    <div class="stat"><div class="stat-num">{len(results)}</div><div class="stat-label">GENRES</div></div>
  </div>
</header>

<div class="toolbar">
  <span class="toolbar-label">FILTER:</span>
  <button class="filter-chip active" onclick="filterGenre('all',this)">ALL</button>
  {''.join(f'<button class="filter-chip" onclick="filterGenre(\'{d["key"]}\',this)">{d["genre"].split()[0]} {d["key"].upper()}</button>' for d in results.values() if d.get("items"))}
  <button class="btn-generate" onclick="openModal()">⚡ GENERATE CODE</button>
</div>

<main id="main-content">
  {genre_sections if genre_sections else '<div class="no-results">No results yet — run discover.py first</div>'}
</main>

<!-- Output Modal -->
<div class="modal" id="output-modal">
  <div class="modal-box">
    <div class="modal-header">
      <div class="modal-title">GENERATED CODE</div>
      <button class="btn-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-tabs">
      <button class="mtab active" onclick="switchMTab('networkshows',this)">networkShows Arrays</button>
      <button class="mtab" onclick="switchMTab('identifiers',this)">Raw Identifiers</button>
      <button class="mtab" onclick="switchMTab('summary',this)">Summary</button>
    </div>
    <div class="modal-body">
      <textarea id="output-text" readonly spellcheck="false"></textarea>
    </div>
    <div class="modal-footer">
      <button class="btn-copy" onclick="copyOutput()">📋 COPY ALL</button>
      <div class="selection-count" id="modal-count"></div>
    </div>
  </div>
</div>

<script>
const RESULTS = {json.dumps(results, ensure_ascii=False)};
let currentAudio = null;
let currentPlayBtn = null;
let currentTab = 'networkshows';

// ── Filter ────────────────────────────────────────────────────────────────
function filterGenre(key, btn) {{
  document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.genre-section').forEach(s => {{
    if (key === 'all' || s.id === 'genre-' + key) s.classList.remove('hidden');
    else s.classList.add('hidden');
  }});
}}

// ── Select helpers ────────────────────────────────────────────────────────
function selectAll(key) {{
  document.querySelectorAll(`[data-genre="${{key}}"] .item-check`).forEach(cb => {{
    cb.checked = true;
    cb.closest('tr').classList.add('selected');
  }});
  updateCount();
}}
function selectNone(key) {{
  document.querySelectorAll(`[data-genre="${{key}}"] .item-check`).forEach(cb => {{
    cb.checked = false;
    cb.closest('tr').classList.remove('selected');
  }});
  updateCount();
}}

document.addEventListener('change', e => {{
  if (e.target.classList.contains('item-check')) {{
    e.target.closest('tr').classList.toggle('selected', e.target.checked);
    updateCount();
  }}
}});

function updateCount() {{
  const n = document.querySelectorAll('.item-check:checked').length;
  document.getElementById('sel-count').textContent = n;
  document.getElementById('modal-count').textContent = n + ' item' + (n!==1?'s':'') + ' selected';
}}

// ── Audio preview ─────────────────────────────────────────────────────────
function playSample(url, btn) {{
  const player = document.getElementById('audio-player');
  if (currentPlayBtn && currentPlayBtn !== btn) {{
    currentPlayBtn.classList.remove('playing');
    currentPlayBtn.textContent = '▶';
  }}
  if (player.src === url && !player.paused) {{
    player.pause();
    btn.classList.remove('playing');
    btn.textContent = '▶';
    currentPlayBtn = null;
    return;
  }}
  player.src = url;
  player.play().then(() => {{
    btn.classList.add('playing');
    btn.textContent = '■';
    currentPlayBtn = btn;
  }}).catch(() => {{
    btn.textContent = '✗';
    setTimeout(() => btn.textContent = '▶', 2000);
  }});
  player.onended = () => {{
    btn.classList.remove('playing');
    btn.textContent = '▶';
    currentPlayBtn = null;
  }};
}}

// ── Generate output ───────────────────────────────────────────────────────
function openModal() {{
  const checked = document.querySelectorAll('.item-check:checked');
  if (!checked.length) {{ alert('Select at least one item first'); return; }}
  generateOutput();
  document.getElementById('output-modal').classList.add('open');
  updateCount();
}}
function closeModal() {{
  document.getElementById('output-modal').classList.remove('open');
}}
document.getElementById('output-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeModal();
}});

function switchMTab(tab, btn) {{
  currentTab = tab;
  document.querySelectorAll('.mtab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  generateOutput();
}}

function generateOutput() {{
  const checked = Array.from(document.querySelectorAll('.item-check:checked'));
  const byStation = {{}};
  const byGenre = {{}};
  const allIds = [];

  checked.forEach(cb => {{
    const id = cb.dataset.id;
    const stations = cb.dataset.stations.split(',').map(Number);
    allIds.push(id);
    stations.forEach(stn => {{
      if (!byStation[stn]) byStation[stn] = [];
      byStation[stn].push(id);
    }});
    const row = cb.closest('tr');
    const genre = row.dataset.genre;
    if (!byGenre[genre]) byGenre[genre] = [];
    byGenre[genre].push(id);
  }});

  let output = '';

  if (currentTab === 'networkshows') {{
    output = '// ═══════════════════════════════════════════════\\n';
    output += '// PASTE THESE INTO YOUR networkShows ARRAYS\\n';
    output += '// in index.html\\n';
    output += '// ═══════════════════════════════════════════════\\n\\n';
    Object.entries(byStation).sort((a,b) => a[0]-b[0]).forEach(([stn, ids]) => {{
      const g = RESULTS[Object.keys(RESULTS).find(k => RESULTS[k].stations?.includes(Number(stn)))] || {{}};
      output += `// Station ${{stn}} — ${{g.genre || '?'}}\\n`;
      ids.forEach(id => output += `"${{id}}",\\n`);
      output += '\\n';
    }});
  }} else if (currentTab === 'identifiers') {{
    output = '// Raw identifiers — one per line\\n\\n';
    allIds.forEach(id => output += id + '\\n');
  }} else {{
    output = '// DISCOVERY SUMMARY\\n';
    output += `// Generated: ${{new Date().toLocaleString()}}\\n`;
    output += `// Total selected: ${{allIds.length}}\\n\\n`;
    Object.entries(byGenre).forEach(([key, ids]) => {{
      const g = RESULTS[key] || {{}};
      output += `${{g.genre || key}}:\\n`;
      ids.forEach(id => {{
        const item = g.items?.find(x => x.identifier === id);
        if (item) output += `  "${{id}}"  // ${{item.title}} (${{item.audio_count}} tracks)\\n`;
      }});
      output += '\\n';
    }});
  }}

  document.getElementById('output-text').value = output;
}}

function copyOutput() {{
  const ta = document.getElementById('output-text');
  ta.select();
  navigator.clipboard.writeText(ta.value).then(() => {{
    const btn = document.querySelector('.btn-copy');
    const orig = btn.textContent;
    btn.textContent = '✓ COPIED!';
    setTimeout(() => btn.textContent = orig, 2000);
  }});
}}
</script>
</body>
</html>'''

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    log(f"✓ HTML review page → {OUTPUT_HTML}")

# ── Run ───────────────────────────────────────────────────────────────────────
def main():
    genre_filter = None
    limit = MAX_PER_GENRE
    resume = '--resume' in sys.argv
    for i, a in enumerate(sys.argv):
        if a == '--genre' and i+1 < len(sys.argv): genre_filter = sys.argv[i+1]
        if a == '--limit' and i+1 < len(sys.argv): limit = int(sys.argv[i+1])

    existing = set()
    if os.path.exists(IDENTIFIERS_FILE):
        with open(IDENTIFIERS_FILE) as f:
            existing = set(json.load(f).keys())
        log(f"Loaded {len(existing)} existing identifiers")

    progress = {}
    if resume and os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)
        log(f"Resuming — {len(progress)} genres done")

    results = progress.copy()
    genres = [g for g in GENRE_CONFIG if not genre_filter or g['key'] == genre_filter]

    for genre in genres:
        key = genre['key']
        if key in results:
            log(f"Skipping {genre['label']} (done)")
            continue

        log(f"\n{'='*55}\n{genre['label']}\n{'='*55}")
        found = {}

        for qi, query in enumerate(genre['queries']):
            log(f"  Query {qi+1}/{len(genre['queries'])}: {query[:60]}...")
            docs = search_archive(query, rows=limit)
            log(f"  → {len(docs)} results")
            for doc in docs:
                iid = doc.get('identifier','')
                if iid and iid not in existing and iid not in found:
                    found[iid] = doc
            time.sleep(REQUEST_DELAY)

        log(f"  {len(found)} unique new candidates")
        verified = []

        for i, (iid, doc) in enumerate(found.items()):
            log(f"  [{(i+1)/len(found)*100:.0f}%] {iid}")
            audio = get_audio_files(iid)
            time.sleep(REQUEST_DELAY)

            if len(audio) < MIN_AUDIO_FILES:
                log(f"    ✗ {len(audio)} audio files"); continue

            if TEST_AUDIO and audio:
                if not test_accessible(audio[0]['url']):
                    log(f"    ✗ not accessible"); continue
                time.sleep(0.3)

            title   = doc.get('title', iid)
            creator = doc.get('creator','')
            if isinstance(creator, list): creator = ', '.join(creator)
            subject = doc.get('subject',[])
            if isinstance(subject, str): subject = [subject]

            log(f"    ✓ {len(audio)} tracks — {title[:50]}")
            verified.append({
                'identifier': iid,
                'title':      title,
                'creator':    creator,
                'date':       str(doc.get('date',''))[:4],
                'downloads':  doc.get('downloads', 0),
                'audio_count': len(audio),
                'subject':    subject[:5],
                'stations':   genre['stations'],
                'genre_key':  key,
                'genre_label': genre['label'],
                'sample_url': audio[0]['url'] if audio else '',
            })

        verified.sort(key=lambda x: (-(x.get('downloads') or 0), -x['audio_count']))
        log(f"\n  ✅ {len(verified)} verified for {genre['label']}")

        results[key] = {
            'genre': genre['label'], 'stations': genre['stations'],
            'key': key, 'items': verified
        }
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(results, f)

    write_html(results)
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    total = sum(len(d.get('items',[])) for d in results.values())
    log(f"\n✅ Done — {total} items found across {len(results)} genres")
    log(f"Open {OUTPUT_HTML} in your browser to review and select content")

if __name__ == '__main__':
    main()
