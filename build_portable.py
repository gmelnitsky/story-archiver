#!/usr/bin/env python3
"""
Build a self-contained, sendable copy of the archive.

Produces  export/Story-Archive/
              Story Archive.html   <- one file, everything inlined
              audio/*.mp3

She unzips it, double-clicks the HTML, and it works — offline, forever, with no
server and no the news site. Transcripts and story text are embedded directly in the page
because browsers block a file:// page from fetching sidecar files.

    python3 scrape/build_portable.py
    python3 scrape/build_portable.py --zip     # also produce the .zip to send
"""

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES, AUDIO, TRANSCRIPTS = ROOT / "data" / "stories", ROOT / "audio", ROOT / "transcripts"
EXPORT = ROOT / "export"
BUNDLE = EXPORT / "Story-Archive"

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{--bg:#faf9f7;--panel:#fff;--ink:#16150f;--muted:#6b6862;--line:#e4e1db;
  --accent:#b03a2e;--accent-soft:#fbeeec;--shadow:0 1px 2px rgba(0,0,0,.05)}
@media (prefers-color-scheme:dark){:root{--bg:#14140f;--panel:#1c1c17;--ink:#f0eee7;
  --muted:#98948b;--line:#2e2d26;--accent:#e8705e;--accent-soft:#2a1a17;
  --shadow:0 1px 2px rgba(0,0,0,.3)}}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 ui-serif,Georgia,'Times New Roman',serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:820px;margin:0 auto;padding:0 20px 80px}
header{padding:56px 0 28px;border-bottom:2px solid var(--ink)}
h1{margin:0;font-size:2.6rem;letter-spacing:-.02em;line-height:1.1}
.sub{color:var(--muted);margin-top:10px;font-size:.95rem;
  font-family:ui-sans-serif,system-ui,sans-serif}
.note{margin-top:14px;padding:11px 14px;background:var(--accent-soft);
  border-left:3px solid var(--accent);border-radius:4px;font-size:.85rem;
  color:var(--muted);font-family:ui-sans-serif,system-ui,sans-serif}
.controls{position:sticky;top:0;z-index:10;background:var(--bg);padding:16px 0;
  border-bottom:1px solid var(--line);display:flex;gap:10px;flex-wrap:wrap;
  align-items:center;font-family:ui-sans-serif,system-ui,sans-serif}
input[type=search],select{font:inherit;font-size:.9rem;padding:9px 12px;
  border:1px solid var(--line);border-radius:7px;background:var(--panel);color:var(--ink)}
input[type=search]{flex:1;min-width:200px}
input:focus,select:focus{outline:2px solid var(--accent);outline-offset:-1px}
.count{color:var(--muted);font-size:.85rem;margin-left:auto;white-space:nowrap}
.story{padding:26px 0;border-bottom:1px solid var(--line)}
.meta{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.72rem;letter-spacing:.09em;
  text-transform:uppercase;color:var(--muted);display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.show{color:var(--accent);font-weight:650}
.story h2{margin:.35em 0 .3em;font-size:1.45rem;line-height:1.25;letter-spacing:-.01em}
.subtitle{margin:0;color:var(--muted);font-size:1rem}
.tools{margin-top:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  font-family:ui-sans-serif,system-ui,sans-serif}
button.tool,a.tool{font:inherit;font-size:.8rem;font-weight:600;cursor:pointer;padding:7px 13px;
  border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);
  text-decoration:none;box-shadow:var(--shadow)}
button.tool:hover,a.tool:hover{border-color:var(--accent);color:var(--accent)}
button.listen{background:var(--accent);border-color:var(--accent);color:#fff}
button.listen:hover{opacity:.88;color:#fff}
audio{width:100%;margin-top:12px;height:38px}
.panel{margin-top:14px;padding:16px 18px;background:var(--accent-soft);
  border-left:3px solid var(--accent);border-radius:4px;max-height:460px;overflow-y:auto;font-size:.95rem}
.panel p{margin:0 0 .75em}
.empty{padding:70px 0;text-align:center;color:var(--muted)}
"""

JS = """
const $=s=>document.querySelector(s);
const list=$('#list'),q=$('#q'),fy=$('#year'),fs=$('#show'),count=$('#count');
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtDate=d=>d?new Date(d+'T12:00:00').toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'}):'';
const fmtDur=s=>s?`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`:'';

function card(s,i){
  const bits=[fmtDate(s.date)];
  if(s.show)bits.push(`<span class="show">${esc(s.show)}</span>`);
  if(s.duration)bits.push(fmtDur(s.duration));
  const t=[];
  if(s.audio)t.push(`<button class="tool listen" data-a="${esc(s.audio)}">▸ Listen</button>`);
  if(s.transcript&&s.transcript.length)t.push(`<button class="tool" data-t="${i}">Transcript</button>`);
  if(s.text&&s.text.length)t.push(`<button class="tool" data-x="${i}">Story text</button>`);
  t.push(`<a class="tool" href="${esc(s.url)}" target="_blank" rel="noopener">Source ↗</a>`);
  return `<article class="story">
    <div class="meta">${bits.join('<span>·</span>')}</div>
    <h2>${esc(s.title)}</h2>
    ${s.subtitle?`<p class="subtitle">${esc(s.subtitle)}</p>`:''}
    <div class="tools">${t.join('')}</div><div class="slot"></div></article>`;
}

function render(){
  const term=q.value.trim().toLowerCase();
  const hits=STORIES.map((s,i)=>[s,i]).filter(([s])=>
    (!fy.value||s.year===fy.value)&&(!fs.value||s.show===fs.value)&&
    (!term||(s.title+' '+s.subtitle).toLowerCase().includes(term)));
  count.textContent=`${hits.length} of ${STORIES.length}`;
  list.innerHTML=hits.length?hits.map(([s,i])=>card(s,i)).join('')
    :'<p class="empty">Nothing matches that.</p>';
}

list.addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b)return;
  const slot=b.closest('.story').querySelector('.slot');
  if(b.dataset.a){
    if(slot.querySelector('audio')){slot.innerHTML='';return;}
    document.querySelectorAll('audio').forEach(a=>a.remove());
    slot.innerHTML=`<audio controls autoplay preload="none" src="${b.dataset.a}"></audio>`;
    return;
  }
  const i=b.dataset.t??b.dataset.x;
  const paras=b.dataset.t!==undefined?STORIES[i].transcript:STORIES[i].text;
  const open=slot.querySelector('.panel');
  if(open){open.remove();return;}
  const d=document.createElement('div');
  d.className='panel';
  d.innerHTML=paras.map(p=>`<p>${esc(p)}</p>`).join('');
  slot.appendChild(d);
});

[q,fy,fs].forEach(el=>el.addEventListener('input',render));
render();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", action="store_true", help="also produce the .zip to send")
    args = ap.parse_args()

    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / "audio").mkdir(exist_ok=True)

    rows, copied = [], 0
    for f in sorted(STORIES.glob("*.json")):
        s = json.loads(f.read_text())
        sid = s["id"]

        audio_rel = ""
        src = AUDIO / f"{sid}.mp3"
        if src.exists() and src.stat().st_size > 0:
            dst = BUNDLE / "audio" / f"{sid}.mp3"
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                dst.unlink(missing_ok=True)
                # Hardlink, don't copy: the bundle then costs ~0 bytes instead of
                # duplicating 1.5 GB of audio. Same file, two names. Zipping and
                # uploading follow the link and see the real bytes.
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)  # different volume — fall back
            audio_rel = f"audio/{sid}.mp3"
            copied += 1

        tx = TRANSCRIPTS / f"{sid}.json"
        rows.append({
            "id": sid,
            "title": s["title"],
            "subtitle": s["teaser"],
            "date": (s["date"] or "")[:10],
            "year": (s["date"] or "")[:4],
            "show": s["show"] or "",
            "url": s["url"],
            "duration": s.get("duration"),
            "audio": audio_rel,
            "transcript": json.loads(tx.read_text()) if tx.exists() else [],
            "text": s.get("paragraphs", []),
        })

    if not rows:
        raise SystemExit("nothing to export yet")

    rows.sort(key=lambda r: r["date"], reverse=True)
    years = sorted({r["year"] for r in rows if r["year"]}, reverse=True)
    shows = sorted({r["show"] for r in rows if r["show"]})
    span = f"{rows[-1]['year']}–{rows[0]['year']}"
    n_audio = sum(1 for r in rows if r["audio"])
    n_tx = sum(1 for r in rows if r["transcript"])

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>the journalist — Story Archive</title><style>{CSS}</style></head><body>
<div class="wrap">
<header>
  <h1>the journalist</h1>
  <p class="sub">{len(rows)} stories, {span} · {n_audio} with audio · {n_tx} transcripts</p>
  <p class="note">This is a private copy, kept on your own computer. The audio plays from
  the <code>audio</code> folder next to this file — keep them together and it all works
  offline, with or without the source site.</p>
</header>
<div class="controls">
  <input type="search" id="q" placeholder="Search titles and subtitles…" autocomplete="off">
  <select id="year"><option value="">All years</option>
    {''.join(f'<option>{y}</option>' for y in years)}</select>
  <select id="show"><option value="">All shows</option>
    {''.join(f'<option>{s}</option>' for s in shows)}</select>
  <span class="count" id="count"></span>
</div>
<main id="list"></main>
</div>
<script>const STORIES={json.dumps(rows, ensure_ascii=False)};</script>
<script>{JS}</script>
</body></html>"""

    out = BUNDLE / "Story Archive.html"
    out.write_text(page, encoding="utf-8")

    size = sum(f.stat().st_size for f in BUNDLE.rglob("*") if f.is_file())
    print(f"bundle: {BUNDLE}")
    print(f"  {len(rows)} stories · {span}")
    print(f"  {n_audio} audio files · {n_tx} transcripts")
    print(f"  page is {out.stat().st_size / 1e6:.1f} MB, whole bundle {size / 1e9:.2f} GB")

    if args.zip:
        z = shutil.make_archive(str(EXPORT / "Story-Archive"), "zip", BUNDLE.parent, BUNDLE.name)
        print(f"  zip: {z}  ({Path(z).stat().st_size / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()
