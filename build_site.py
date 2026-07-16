#!/usr/bin/env python3
"""
Build the local browsable archive from data/stories/*.json.

    python3 scrape/build_site.py

Story metadata is inlined into index.html so the page needs no network at all.
Transcripts are fetched on demand from transcripts/ — they're big and most
visits won't open one.
"""

import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES, SITE, AUDIO = ROOT / "data" / "stories", ROOT / "site", ROOT / "audio"


def load():
    rows = []
    for f in sorted(STORIES.glob("*.json")):
        s = json.loads(f.read_text())
        local = AUDIO / f"{s['id']}.mp3"
        rows.append({
            "id": s["id"],
            "title": s["title"],
            "subtitle": s["teaser"],
            "date": (s["date"] or "")[:10],
            "year": (s["date"] or "")[:4],
            "show": s["show"] or "",
            "byline": s["byline"],
            "url": s["url"],
            # Prefer the mp3 we actually own; fall back to the site's copy.
            "audio": f"../audio/{s['id']}.mp3" if local.exists() else (s["audio_url"] or ""),
            "audio_is_local": local.exists(),
            "duration": s.get("duration"),
            "transcript": s.get("has_transcript", False),
            "words": s.get("word_count", 0),
        })
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#faf9f7; --panel:#fff; --ink:#16150f; --muted:#6b6862; --line:#e4e1db;
  --accent:#b03a2e; --accent-soft:#fbeeec; --shadow:0 1px 2px rgba(0,0,0,.05);
}
@media (prefers-color-scheme:dark){
  :root{--bg:#14140f;--panel:#1c1c17;--ink:#f0eee7;--muted:#98948b;--line:#2e2d26;
        --accent:#e8705e;--accent-soft:#2a1a17;--shadow:0 1px 2px rgba(0,0,0,.3)}
}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 ui-serif,Georgia,'Times New Roman',serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:820px;margin:0 auto;padding:0 20px 80px}

header{padding:56px 0 28px;border-bottom:2px solid var(--ink)}
h1{margin:0;font-size:2.6rem;letter-spacing:-.02em;line-height:1.1}
.sub{color:var(--muted);margin-top:10px;font-size:.95rem;
  font-family:ui-sans-serif,system-ui,sans-serif}

.controls{position:sticky;top:0;z-index:10;background:var(--bg);
  padding:16px 0;border-bottom:1px solid var(--line);
  display:flex;gap:10px;flex-wrap:wrap;align-items:center;
  font-family:ui-sans-serif,system-ui,sans-serif}
input[type=search],select{font:inherit;font-size:.9rem;padding:9px 12px;
  border:1px solid var(--line);border-radius:7px;background:var(--panel);color:var(--ink)}
input[type=search]{flex:1;min-width:200px}
input[type=search]:focus,select:focus{outline:2px solid var(--accent);outline-offset:-1px}
.count{color:var(--muted);font-size:.85rem;margin-left:auto;white-space:nowrap}

.story{padding:26px 0;border-bottom:1px solid var(--line)}
.meta{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.72rem;
  letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
  display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.show{color:var(--accent);font-weight:650}
.story h2{margin:.35em 0 .3em;font-size:1.45rem;line-height:1.25;letter-spacing:-.01em}
.story h2 a{color:inherit;text-decoration:none}
.story h2 a:hover{text-decoration:underline;text-decoration-color:var(--accent)}
.subtitle{margin:0;color:var(--muted);font-size:1rem}

.tools{margin-top:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  font-family:ui-sans-serif,system-ui,sans-serif}
button.tool,a.tool{font:inherit;font-size:.8rem;font-weight:600;cursor:pointer;
  padding:7px 13px;border-radius:999px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);text-decoration:none;box-shadow:var(--shadow)}
button.tool:hover,a.tool:hover{border-color:var(--accent);color:var(--accent)}
button.listen{background:var(--accent);border-color:var(--accent);color:#fff}
button.listen:hover{opacity:.88;color:#fff}
.local{font-size:.66rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
audio{width:100%;margin-top:12px;height:38px}
.transcript{margin-top:14px;padding:16px 18px;background:var(--accent-soft);
  border-left:3px solid var(--accent);border-radius:4px;max-height:420px;overflow-y:auto;
  font-size:.95rem}
.transcript p{margin:0 0 .75em}
.empty{padding:70px 0;text-align:center;color:var(--muted)}
[hidden]{display:none !important}
"""

JS = """
const $ = (s) => document.querySelector(s);
const list = $('#list'), q = $('#q'), fy = $('#year'), fs = $('#show'), count = $('#count');

const esc = (s) => (s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtDate = (d) => d ? new Date(d + 'T12:00:00').toLocaleDateString('en-US',
  {year:'numeric', month:'long', day:'numeric'}) : '';
const fmtDur = (s) => s ? `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}` : '';

function card(s) {
  const bits = [fmtDate(s.date)];
  if (s.show) bits.push(`<span class="show">${esc(s.show)}</span>`);
  if (s.duration) bits.push(fmtDur(s.duration));

  const tools = [];
  if (s.audio) tools.push(
    `<button class="tool listen" data-audio="${esc(s.audio)}">▸ Listen</button>` +
    (s.audio_is_local ? '<span class="local">saved locally</span>'
                      : '<span class="local">streams from the source</span>'));
  if (s.transcript) tools.push(`<button class="tool" data-transcript="${s.id}">Transcript</button>`);
  tools.push(`<a class="tool" href="${esc(s.url)}" target="_blank" rel="noopener">Source ↗</a>`);

  return `<article class="story">
    <div class="meta">${bits.join('<span>·</span>')}</div>
    <h2><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></h2>
    ${s.subtitle ? `<p class="subtitle">${esc(s.subtitle)}</p>` : ''}
    <div class="tools">${tools.join('')}</div>
    <div class="slot"></div>
  </article>`;
}

function render() {
  const term = q.value.trim().toLowerCase();
  const hits = STORIES.filter(s =>
    (!fy.value || s.year === fy.value) &&
    (!fs.value || s.show === fs.value) &&
    (!term || (s.title + ' ' + s.subtitle).toLowerCase().includes(term)));

  count.textContent = `${hits.length} of ${STORIES.length}`;
  list.innerHTML = hits.length
    ? hits.map(card).join('')
    : '<p class="empty">Nothing matches that.</p>';
}

// One player at a time — clicking Listen anywhere stops whatever else was going.
list.addEventListener('click', async (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const slot = btn.closest('.story').querySelector('.slot');

  if (btn.dataset.audio) {
    if (slot.querySelector('audio')) { slot.innerHTML = ''; return; }
    document.querySelectorAll('audio').forEach(a => a.remove());
    slot.innerHTML = `<audio controls autoplay preload="none" src="${btn.dataset.audio}"></audio>`;
    slot.querySelector('audio').onerror = () => {
      slot.innerHTML = '<p class="subtitle">The source no longer serves this audio. ' +
        'Re-run the scraper with --audio to keep the ones still up.</p>';
    };
  }

  if (btn.dataset.transcript) {
    const open = slot.querySelector('.transcript');
    if (open) { open.remove(); return; }
    const r = await fetch(`../transcripts/${btn.dataset.transcript}.json`);
    const paras = await r.json();
    const div = document.createElement('div');
    div.className = 'transcript';
    div.innerHTML = paras.map(p => `<p>${esc(p)}</p>`).join('');
    slot.appendChild(div);
  }
});

[q, fy, fs].forEach(el => el.addEventListener('input', render));
render();
"""


def main():
    rows = load()
    if not rows:
        raise SystemExit("no stories yet — run scrape.py first")

    SITE.mkdir(exist_ok=True)
    years = sorted({r["year"] for r in rows if r["year"]}, reverse=True)
    shows = sorted({r["show"] for r in rows if r["show"]})

    with_audio = sum(1 for r in rows if r["audio"])
    local_audio = sum(1 for r in rows if r["audio_is_local"])
    with_tx = sum(1 for r in rows if r["transcript"])
    span = f"{rows[-1]['year']}–{rows[0]['year']}"

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>the journalist — Story Archive</title>
<style>{CSS}</style></head><body>
<div class="wrap">
<header>
  <h1>the journalist</h1>
  <p class="sub">{len(rows)} stories, {span} · {with_audio} with audio
    ({local_audio} saved locally) · {with_tx} transcripts</p>
</header>

<div class="controls">
  <input type="search" id="q" placeholder="Search titles and subtitles…" autocomplete="off">
  <select id="year"><option value="">All years</option>
    {''.join(f'<option>{y}</option>' for y in years)}</select>
  <select id="show"><option value="">All shows</option>
    {''.join(f'<option>{html.escape(s)}</option>' for s in shows)}</select>
  <span class="count" id="count"></span>
</div>

<main id="list"></main>
</div>
<script>const STORIES = {json.dumps(rows, ensure_ascii=False)};</script>
<script>{JS}</script>
</body></html>"""

    out = SITE / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"built {out}")
    print(f"  {len(rows)} stories · {span}")
    print(f"  {with_audio} with audio ({local_audio} saved locally, {with_audio - local_audio} streaming from the news site)")
    print(f"  {with_tx} transcripts · {len(shows)} shows")


if __name__ == "__main__":
    main()
