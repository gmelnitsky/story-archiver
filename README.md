# Story Archiver

[![CI](https://github.com/gmelnitsky/story-archiver/actions/workflows/ci.yml/badge.svg)](https://github.com/gmelnitsky/story-archiver/actions/workflows/ci.yml)

A retiring journalist wanted to keep her life's work — a career's worth of
published stories, audio, and transcripts — before she stepped away and lost
easy access to it. So I built her a way to save all of it into a single personal
file on her own computer: one that opens forever, offline, with no account, no
server, and no dependence on the original site staying online.

This is that toolchain.

> **Code only.** This repository is the tooling, not the archive. The stories,
> audio, and transcripts are the publisher's copyrighted content — they are
> never committed or redistributed here; they live only on the owner's machine.
> All site names and IDs in the code are placeholders.

## What it does

```
collect-urls.js   → scrape.py       → build_site.py        → build_portable.py
(gather her URLs)   (download each)   (browsable local copy)  (one offline file)
```

1. **`collect-urls.js`** — run in the browser on her author page. It scrolls and
   collects the links to her stories *at normal reading pace, in the browser* —
   no pounding on anyone's server — and saves them to a file.
2. **`scrape.py`** — downloads each story to her disk: the text, the audio, and
   the transcript where one exists. Resumable, so re-running only fetches what's
   missing. For her earliest pieces there's barely any web text — just a
   headline and the tape — so the audio *is* the story, and it gets saved rather
   than merely linked.
3. **`build_site.py`** — assembles a clean, browsable local website over
   everything, entirely on her own machine.
4. **`build_portable.py`** — the part I'm proudest of: it folds the *entire*
   archive — every story, transcript, and asset — into a **single HTML file**.
   Browsers won't let a `file://` page load sidecar files, so everything is
   embedded inline. The result is one document she can double-click and read
   forever, offline, even if the original site disappears.

## Why build it this way

- **It has to outlive its source.** The whole point was permanence: the finished
  archive depends on nothing — not a server, not the network, not the original
  site continuing to exist. A link rots; a self-contained file doesn't.
- **Gentle by design.** URLs are gathered client-side at reading speed, and the
  downloader is resumable and unhurried rather than aggressive.
- **Personal and private.** It was built for one person to keep her own work.
  Nothing is republished, and the archive itself never leaves her computer.

## Usage

```sh
# 1. Paste collect-urls.js into your browser console on the author's page.
# 2. Point the config at the right site/author, then:
python3 scrape.py                 # download everything (resumable)
python3 build_site.py             # build the browsable local site
python3 build_portable.py --zip   # produce the single-file offline archive
```

## Tests

The suite runs entirely offline on tiny inline HTML/JSON fixtures — no network,
no live site, and no copyrighted content (the archive itself is never committed).
It covers the pure, load-bearing logic:

- **Stable IDs / safe filenames** (`scrape.story_id`) — the same story always
  maps to the same id regardless of its trailing slug (this is what makes the
  scraper's resume-on-restart correct), and any un-dated URL still yields a
  bounded, sanitized filename.
- **Content extraction** (`scrape.parse_story` / `parse_transcript`) — prefer
  structured `ld+json` metadata over page markup, strip page furniture, dedupe
  bylines in order, resolve the *named* transcript link rather than the bare nav
  one, and pick the transcript container that actually holds the text.
- **Site assembly** (`build_site`) — stories are ordered newest-first, a
  locally-saved mp3 is preferred over the remote URL, and the story index is
  inlined into `index.html` so the page renders with no network.
- **The portable bundle** (`build_portable`) — the core promise: exactly one
  self-contained HTML file, with story text and transcripts embedded inline (a
  `file://` page can't fetch sidecars), newest-first ordering, and audio bundled
  alongside as a relative link.

Run them:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

CI (GitHub Actions) runs the same suite on Python 3.11, 3.12, and 3.13 on every
push and pull request.

## Tech

Python (standard-library scraping and HTML assembly) · a browser-side URL
collector in vanilla JS · zero-dependency, self-contained single-file HTML output.
