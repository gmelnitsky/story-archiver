#!/usr/bin/env python3
"""
Render a shareable snapshot of archive progress.

Contains only counts, years, and percentages — no the news site headlines, text, or audio —
so it's safe to publish. Re-run to refresh the numbers, then redeploy.

    python3 scrape/build_public.py
"""

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "progress.html"

try:
    s = json.load(urllib.request.urlopen("http://localhost:8124/api/status", timeout=5))
except Exception:
    sys.exit("dashboard isn't running — start scrape/dashboard.py first")

pct = s["done"] / s["total"] * 100 if s["total"] else 0
stamp = datetime.now().strftime("%b %-d, %Y at %-I:%M %p")
complete = not s["running"] and s["done"] >= s["total"] and s["total"]

state_label = "Complete" if complete else ("Archiving" if s["running"] else "Paused")
state_class = "done" if complete else ("live" if s["running"] else "idle")

years = s["years"]
peak = max((y["want"] for y in years), default=1)
bars = "".join(
    f'<div class="yr" style="--t:{y["want"] / peak * 100:.1f}%;'
    f'--f:{(y["have"] / y["want"] * 100) if y["want"] else 0:.1f}%">'
    f'<div class="track"><div class="fill"></div></div>'
    f'<span class="lbl">{y["year"][2:]}</span>'
    f'<span class="tip">{y["year"]} · {y["have"]} of {y["want"]}</span></div>'
    for y in years
)

span = f'{years[0]["year"]}–{years[-1]["year"]}' if years else "—"

HTML = f"""<title>the journalist — Story Archive Progress</title>
<style>
  *,*::before,*::after{{box-sizing:border-box}}
  :root{{
    color-scheme:light;
    --plane:#f4f2ee; --card:#fbfaf8; --ink:#1b1a17; --ink-2:#57544d; --ink-3:#8a8579;
    --line:#e0dcd3; --rule:rgba(27,26,23,.10);
    --signal:#a8620c; --track:#e5e0d6;
    --good:#0e7a35;
  }}
  @media (prefers-color-scheme:dark){{
    :root:not([data-theme="light"]){{
      color-scheme:dark;
      --plane:#14130f; --card:#1c1b17; --ink:#f5f2ea; --ink-2:#b6b1a4; --ink-3:#8a8579;
      --line:#2b2a24; --rule:rgba(245,242,234,.12);
      --signal:#e8a54a; --track:#2b2a24; --good:#4cc272;
    }}
  }}
  :root[data-theme="dark"]{{
    color-scheme:dark;
    --plane:#14130f; --card:#1c1b17; --ink:#f5f2ea; --ink-2:#b6b1a4; --ink-3:#8a8579;
    --line:#2b2a24; --rule:rgba(245,242,234,.12);
    --signal:#e8a54a; --track:#2b2a24; --good:#4cc272;
  }}

  body{{margin:0;background:var(--plane);color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.55}}
  .wrap{{max-width:780px;margin:0 auto;padding:56px 24px 72px;
    display:flex;flex-direction:column;gap:30px}}
  .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
    font-variant-numeric:tabular-nums}}

  header{{display:flex;flex-direction:column;gap:10px}}
  .eyebrow{{font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
  h1{{margin:0;font-size:clamp(1.9rem,5vw,2.5rem);letter-spacing:-.02em;
    text-wrap:balance;font-weight:640}}
  .lede{{margin:0;color:var(--ink-2);max-width:60ch}}

  .pill{{align-self:flex-start;display:inline-flex;align-items:center;gap:7px;
    padding:5px 11px;border:1px solid var(--rule);border-radius:999px;
    font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;font-weight:700;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
  .dot{{width:7px;height:7px;border-radius:50%;background:var(--ink-3)}}
  .live .dot{{background:var(--signal);animation:blink 1.7s ease-in-out infinite}}
  .done .dot{{background:var(--good)}}
  .live{{color:var(--signal)}} .done{{color:var(--good)}}
  @keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}

  .meter{{display:flex;flex-direction:column;gap:9px}}
  .bar{{height:10px;background:var(--track);border-radius:999px;overflow:hidden}}
  .bar>i{{display:block;height:100%;width:{pct:.1f}%;background:var(--signal);
    border-radius:999px;animation:grow 1.1s cubic-bezier(.4,0,.2,1) both}}
  @keyframes grow{{from{{width:0}}}}
  .meter .row{{display:flex;justify-content:space-between;font-size:.85rem;color:var(--ink-2)}}

  .tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}}
  .tile{{background:var(--card);border:1px solid var(--rule);border-radius:9px;padding:15px 17px;
    display:flex;flex-direction:column;gap:3px}}
  .tile .k{{font-size:.66rem;letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3);
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
  .tile .v{{font-size:1.75rem;font-weight:650;letter-spacing:-.02em;line-height:1.15}}
  .tile .n{{font-size:.78rem;color:var(--ink-2)}}

  .card{{background:var(--card);border:1px solid var(--rule);border-radius:9px;padding:20px 22px;
    display:flex;flex-direction:column;gap:4px}}
  .card h2{{margin:0;font-size:.95rem;font-weight:650}}
  .card .cap{{margin:0 0 16px;font-size:.8rem;color:var(--ink-3)}}
  .chart{{display:flex;align-items:flex-end;gap:2px;height:150px;overflow-x:auto;padding-top:20px}}
  .yr{{flex:1;min-width:16px;height:100%;display:flex;flex-direction:column;
    justify-content:flex-end;align-items:center;gap:6px;position:relative}}
  .yr .track{{width:100%;height:var(--t);background:var(--track);border-radius:3px 3px 0 0;
    display:flex;align-items:flex-end;min-height:3px}}
  .yr .fill{{width:100%;height:var(--f);background:var(--signal);border-radius:3px 3px 0 0;
    animation:rise .9s cubic-bezier(.4,0,.2,1) both}}
  @keyframes rise{{from{{height:0}}}}
  .yr .lbl{{font-size:.6rem;color:var(--ink-3);
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
  .yr .tip{{position:absolute;bottom:calc(100% - 14px);left:50%;transform:translateX(-50%);
    background:var(--ink);color:var(--plane);font-size:.68rem;padding:4px 8px;border-radius:5px;
    white-space:nowrap;opacity:0;pointer-events:none;transition:opacity .12s;z-index:3;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
  .yr:hover .tip,.yr:focus-within .tip{{opacity:1}}

  .notes{{border-top:1px solid var(--rule);padding-top:22px;
    display:flex;flex-direction:column;gap:11px;font-size:.9rem;color:var(--ink-2)}}
  .notes b{{color:var(--ink);font-weight:640}}
  footer{{color:var(--ink-3);font-size:.78rem;border-top:1px solid var(--rule);padding-top:16px}}

  @media (prefers-reduced-motion:reduce){{
    *{{animation:none !important;transition:none !important}}
  }}
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">{'Archive complete' if complete else 'Archive in progress'}</div>
    <h1>the journalist — the news site</h1>
    <p class="lede">{'A private, offline copy of a lifetime of reporting — now safe independently of the news site.' if complete else 'Building a private, offline copy of a lifetime of reporting, so it survives independently of the news site.'}</p>
    <span class="pill {state_class}"><span class="dot"></span>{state_label}</span>
  </header>

  <div class="meter">
    <div class="bar"><i></i></div>
    <div class="row">
      <span class="mono">{s['done']} / {s['total']} stories</span>
      <span class="mono">{pct:.1f}%</span>
    </div>
  </div>

  <div class="tiles">
    <div class="tile"><span class="k">Stories</span>
      <span class="v mono">{s['done']}</span><span class="n">of {s['total']} on the news site</span></div>
    <div class="tile"><span class="k">Audio saved</span>
      <span class="v mono">{s['audio']}</span><span class="n">{s['audio_gb']} GB of tape</span></div>
    <div class="tile"><span class="k">Transcripts</span>
      <span class="v mono">{s['transcripts']}</span><span class="n">where one exists</span></div>
    <div class="tile"><span class="k">Failures</span>
      <span class="v mono">{s['failed']}</span><span class="n">{'none — clean run' if not s['failed'] else 'see log'}</span></div>
  </div>

  <div class="card">
    <h2>Her career, by year</h2>
    <p class="cap">Filled = saved · track = what the site lists · {span}</p>
    <div class="chart">{bars}</div>
  </div>

  <div class="notes">
    <p style="margin:0"><b>Why the audio, not just links.</b> Her early pieces have no
      transcript and almost no web text — a headline, a one-line summary, and the tape.
      For those years the audio <em>is</em> the story, so it gets downloaded rather than
      linked. The site still serves those old mp3s today; that's theirs to change.</p>
    <p style="margin:0"><b>Where it starts.</b> It reaches as far back as the news site's
      own archive goes. Earlier work isn't on their site to recover.</p>
    <p style="margin:0"><b>What this page is.</b> Progress only: counts and dates. The
      archive itself is private and stays on disk.</p>
  </div>

  <footer class="mono">Snapshot — {stamp}</footer>
</div>
"""

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT}")
print(f"  {s['done']}/{s['total']} · {pct:.1f}% · {state_label}")
