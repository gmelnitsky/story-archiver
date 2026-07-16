#!/usr/bin/env python3
"""
Live progress dashboard for the the journalist archive.

    python3 scrape/dashboard.py     ->  http://localhost:8124

Reads state straight off disk, so it's accurate whether or not the scraper is
running, and it survives the scraper being stopped and resumed.
"""

import http.server
import json
import re
import socketserver
import subprocess
import time
import webbrowser
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, AUDIO, TRANSCRIPTS = ROOT / "data", ROOT / "audio", ROOT / "transcripts"
STORIES = DATA / "stories"
PORT = 8124

START = time.time()
_seen_at_start = None


def status():
    global _seen_at_start

    urls = json.loads((DATA / "urls.json").read_text()) if (DATA / "urls.json").exists() else []
    total = len(urls)

    done_files = list(STORIES.glob("*.json"))
    done = len(done_files)
    if _seen_at_start is None:
        _seen_at_start = done

    mp3s = list(AUDIO.glob("*.mp3"))
    audio_bytes = sum(f.stat().st_size for f in mp3s)
    n_tx = len(list(TRANSCRIPTS.glob("*.json")))

    running = bool(
        subprocess.run(["pgrep", "-f", "scrape/scrape.py"], capture_output=True).stdout.strip()
    )

    # Rate measured over this dashboard's own uptime — honest about what it knows.
    elapsed = max(time.time() - START, 1)
    made = max(done - _seen_at_start, 0)
    rate = made / (elapsed / 60) if elapsed > 20 and made else 0
    eta = round((total - done) / rate) if rate > 0.2 and done < total else None

    # Expected vs archived, per year.
    want = Counter(m.group(1) for u in urls if (m := re.search(r"/(\d{4})/", u)))
    have = Counter()
    latest = ""
    for f in done_files:
        try:
            s = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        d = (s.get("date") or "")[:10]
        if d:
            have[d[:4]] += 1
            latest = max(latest, d)

    years = sorted(want)
    log = DATA / "scrape.log"
    failed = log.read_text().count("FAILED") if log.exists() else 0

    return {
        "total": total,
        "done": done,
        "audio": len(mp3s),
        "audio_gb": round(audio_bytes / 1e9, 2),
        "transcripts": n_tx,
        "running": running,
        "rate": round(rate, 1),
        "eta": eta,
        "failed": failed,
        "latest": latest,
        "years": [{"year": y, "want": want[y], "have": have.get(y, 0)} for y in years],
        "zip": (ROOT / "export" / "Story-Archive.zip").exists(),
    }


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>the journalist Archive — Progress</title>
<style>
  *,*::before,*::after{box-sizing:border-box}
  /* Tokens live on :root — body uses them, and body is not inside .viz-root.
     Scoping them to a descendant left body with no background and no text color,
     which rendered as black-on-black in dark mode. */
  :root{
    color-scheme:light;
    --surface-1:#fcfcfb; --plane:#f9f9f7;
    --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
    --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
    --series-1:#2a78d6; --track:#e1e0d9;
    --good:#0ca30c; --warning:#fab219;
  }
  @media (prefers-color-scheme:dark){
    :root:not([data-theme="light"]){
      color-scheme:dark;
      --surface-1:#1a1a19; --plane:#0d0d0d;
      --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#a3a199;
      --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
      --series-1:#3987e5; --track:#2c2c2a;
    }
  }
  :root[data-theme="dark"]{
    color-scheme:dark;
    --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#a3a199;
    --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
    --series-1:#3987e5; --track:#2c2c2a;
  }
  body{margin:0;background:var(--plane);color:var(--text-primary);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  .wrap{max-width:900px;margin:0 auto;padding:40px 24px 64px}
  h1{margin:0;font-size:1.6rem;letter-spacing:-.01em}
  .head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
  .state{font-size:.75rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
    display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;
    border:1px solid var(--border)}
  .dot{width:8px;height:8px;border-radius:50%}
  .live .dot{background:var(--good);animation:pulse 1.6s ease-in-out infinite}
  .idle .dot{background:var(--muted)}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .sub{color:var(--text-secondary);font-size:.9rem;margin-top:6px}

  .bar-outer{margin-top:26px;height:12px;background:var(--track);border-radius:999px;overflow:hidden}
  .bar-inner{height:100%;background:var(--series-1);border-radius:999px;
    transition:width .6s cubic-bezier(.4,0,.2,1)}
  .bar-meta{display:flex;justify-content:space-between;margin-top:8px;
    font-size:.85rem;color:var(--text-secondary)}

  .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:12px;margin-top:28px}
  .tile{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
  .tile .label{font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
  .tile .val{font-size:1.9rem;font-weight:650;margin-top:6px;line-height:1.1;letter-spacing:-.02em}
  .tile .foot{font-size:.78rem;color:var(--text-secondary);margin-top:3px}

  .card{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;
    padding:20px 22px;margin-top:24px;overflow-x:auto}
  .card h2{margin:0 0 2px;font-size:1rem}
  .card .cap{color:var(--muted);font-size:.8rem;margin:0 0 18px}
  .chart{display:flex;align-items:flex-end;gap:3px;height:170px;min-width:640px}
  .col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
    height:100%;position:relative}
  .col .track{width:100%;background:var(--track);border-radius:4px 4px 0 0;position:relative;
    display:flex;align-items:flex-end}
  .col .fill{width:100%;background:var(--series-1);border-radius:4px 4px 0 0;
    transition:height .6s cubic-bezier(.4,0,.2,1)}
  .col .yr{font-size:.62rem;color:var(--muted);margin-top:7px;
    writing-mode:vertical-rl;transform:rotate(180deg);font-variant-numeric:tabular-nums}
  .col:hover .tip{opacity:1}
  .tip{position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%);
    background:var(--text-primary);color:var(--surface-1);font-size:.72rem;
    padding:5px 9px;border-radius:6px;white-space:nowrap;opacity:0;pointer-events:none;
    transition:opacity .12s;z-index:5;font-variant-numeric:tabular-nums}
  .done-note{margin-top:22px;padding:14px 16px;border-radius:8px;
    background:var(--surface-1);border:1px solid var(--good);font-size:.9rem}
</style></head>
<body><div class="viz-root"><div class="wrap">

<div class="head">
  <h1>the journalist Archive</h1>
  <span class="state idle" id="state"><span class="dot"></span><span id="stateTxt">…</span></span>
</div>
<p class="sub" id="sub">Loading…</p>

<div class="bar-outer"><div class="bar-inner" id="bar" style="width:0%"></div></div>
<div class="bar-meta"><span id="pct">—</span><span id="eta"></span></div>

<div class="tiles" id="tiles"></div>

<div class="card">
  <h2>Coverage by year</h2>
  <p class="cap">Filled = archived · track = stories the site lists for that year</p>
  <div class="chart" id="chart"></div>
</div>

<div id="doneNote"></div>

</div></div>
<script>
const $ = (s) => document.querySelector(s);

function tile(label, val, foot='') {
  return `<div class="tile"><div class="label">${label}</div>
    <div class="val">${val}</div>${foot ? `<div class="foot">${foot}</div>` : ''}</div>`;
}

async function tick() {
  const s = await (await fetch('/api/status')).json();
  const pct = s.total ? (s.done / s.total * 100) : 0;

  $('#state').className = 'state ' + (s.running ? 'live' : 'idle');
  $('#stateTxt').textContent = s.running ? 'Scraping' : (s.done >= s.total && s.total ? 'Complete' : 'Stopped');
  $('#sub').textContent = s.latest
    ? `Working through ${new Date(s.latest + 'T12:00:00').toLocaleDateString('en-US',{month:'long',year:'numeric'})}`
    : 'Waiting to start';

  $('#bar').style.width = pct + '%';
  $('#pct').textContent = `${s.done} of ${s.total} stories · ${pct.toFixed(1)}%`;
  $('#eta').textContent = s.eta != null ? `~${s.eta} min left · ${s.rate}/min`
                        : (s.running ? 'measuring rate…' : '');

  $('#tiles').innerHTML =
    tile('Stories', s.done, `of ${s.total}`) +
    tile('Audio', s.audio, `${s.audio_gb} GB on disk`) +
    tile('Transcripts', s.transcripts, 'where one exists') +
    tile('Failures', s.failed, s.failed ? 'check scrape.log' : 'none');

  const max = Math.max(...s.years.map(y => y.want), 1);
  $('#chart').innerHTML = s.years.map(y => {
    const th = (y.want / max * 100);
    const fh = y.want ? (y.have / y.want * 100) : 0;
    return `<div class="col">
      <div class="tip">${y.year} — ${y.have}/${y.want} archived</div>
      <div class="track" style="height:${th}%">
        <div class="fill" style="height:${fh}%"></div>
      </div>
      <div class="yr">${y.year}</div>
    </div>`;
  }).join('');

  $('#doneNote').innerHTML = (!s.running && s.total && s.done >= s.total)
    ? `<div class="done-note"><strong>Archive complete.</strong> ${s.done} stories, ${s.audio} audio files, ${s.transcripts} transcripts.
       ${s.zip ? 'The zip is ready in <code>export/</code> — upload it to Drive and share it with them.'
               : 'Building the bundle…'}</div>`
    : '';
}

tick();
setInterval(tick, 3000);
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/status"):
            body = json.dumps(status()).encode()
            ctype = "application/json"
        else:
            body = PAGE.encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # keep the terminal quiet


# Without this, restarting the dashboard fails with "Address already in use" for a
# minute while the old socket sits in TIME_WAIT.
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    url = f"http://localhost:{PORT}"
    print(f"dashboard → {url}\nCtrl-C to stop.")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
