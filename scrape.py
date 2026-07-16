#!/usr/bin/env python3
"""
Archive the journalist's the news site work to local disk.

Reads data/urls.json (produced by collect-urls.js in the browser) and, for each
story, saves the raw page, the parsed text + metadata, the transcript, and the
aired audio.

Resumable: anything already on disk is skipped, so you can stop and restart
freely. Raw HTML is kept for every story, so a parser fix later never means
re-fetching the site.

    python3 scrape/scrape.py                 # everything
    python3 scrape/scrape.py --limit 20      # dry-ish run over the first 20
    python3 scrape/scrape.py --no-audio      # text + transcripts only (fast)
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA, RAW, TRANSCRIPTS, AUDIO = (ROOT / d for d in ("data", "raw", "transcripts", "audio"))
STORIES = DATA / "stories"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# the site's markup has unclosed tags. Python's built-in html.parser responds by nesting
# each <p> inside the one before it, so every paragraph swallows its siblings and the
# text comes out duplicated many times over. html5lib parses it the way a browser
# does. Do not "simplify" this back to the default parser.
PARSER = "html5lib"

# Chrome, blocks that are page furniture rather than the story itself.
NOT_BODY = (
    ".bucketwrap, .imagewrap, .captionwrap, .credit-caption, .caption, .credit, "
    "figure, aside, script, style, .ad-wrap, .callout, .enlarge-options, "
    ".hide-caption, .story-footer, .newsletter-signup, .internallink"
)

session = requests.Session()
session.headers["User-Agent"] = UA


def story_id(url: str) -> str:
    """.../2025/10/24/nx-s1-5581432/boston-bar-... -> nx-s1-5581432"""
    parts = [p for p in url.split("/") if p]
    for i, p in enumerate(parts):
        if re.fullmatch(r"\d{4}", p) and i + 3 < len(parts):
            return parts[i + 3]
    return re.sub(r"\W+", "-", url)[-40:]


def get(url: str, tries: int = 3, timeout: int = 30):
    """Fetch with retry + backoff. Returns None rather than raising."""
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == tries:
                print(f"      ! giving up on {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2**attempt)
    return None


def parse_story(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, PARSER)

    # Structured metadata the site embeds for search engines — cleanest source available.
    ld = {}
    tag = soup.find("script", type="application/ld+json")
    if tag and tag.string:
        try:
            ld = json.loads(tag.string)
        except json.JSONDecodeError:
            pass

    h1 = soup.find("h1")
    title = ld.get("headline") or (h1.get_text(strip=True) if h1 else "")

    date = ld.get("datePublished") or ""
    if not date:
        t = soup.find("time", attrs={"datetime": True})
        date = t["datetime"] if t else ""

    byline = [b.get_text(strip=True) for b in soup.select(".byline__name")]
    if not byline and isinstance(ld.get("author"), dict):
        byline = [ld["author"].get("name", "")]
    byline = [b for b in dict.fromkeys(byline) if b]

    show = ""
    slug = soup.select_one(".slug-wrap .slug, .slug-wrap a")
    if slug:
        show = slug.get_text(strip=True)

    body = soup.find("div", id="storytext")

    images = []
    if body:
        for wrap in body.select(".bucketwrap.image, .imagewrap"):
            img = wrap.find("img")
            if not img:
                continue
            src = img.get("src") or img.get("data-original") or ""
            if not src.startswith("http"):
                continue
            cap = wrap.find_parent().select_one(".caption, .credit-caption")
            images.append({
                "src": src,
                "caption": cap.get_text(" ", strip=True) if cap else "",
            })

    paragraphs = []
    if body:
        for junk in body.select(NOT_BODY):
            junk.decompose()
        for p in body.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    audio_url, duration = "", None
    mod = soup.find(attrs={"data-audio": True})
    if mod:
        try:
            meta = json.loads(mod["data-audio"])
            if meta.get("available", True):
                audio_url = meta.get("audioUrl", "") or ""
                duration = meta.get("duration")
        except (json.JSONDecodeError, KeyError):
            pass

    # Every page carries a bare "/transcripts/" nav link. Matching that instead of
    # the story's own link sent us to an empty landing page — and cost a wasted request
    # on all 702 stories. Insist on a link that actually names a story.
    transcript_url = ""
    link = soup.find("a", href=re.compile(r"/transcripts/[\w-]+"))
    if link:
        transcript_url = requests.compat.urljoin(url, link["href"])

    return {
        "id": story_id(url),
        "url": url,
        "title": title,
        "date": date,
        "byline": byline,
        "show": show,
        "teaser": ld.get("description", ""),
        "paragraphs": paragraphs,
        "word_count": sum(len(p.split()) for p in paragraphs),
        "images": images,
        "audio_url": audio_url,
        "duration": duration,
        "transcript_url": transcript_url,
        "has_transcript": False,
        "has_audio": False,
    }


def parse_transcript(html: str) -> list[str]:
    soup = BeautifulSoup(html, PARSER)

    # Transcript pages carry several elements matching ".transcript" — including an
    # empty wrapper that sits earlier in the document than the real one. Selector
    # groups resolve in document order, so asking for the first match hands back the
    # empty one. Take whichever candidate actually holds the most paragraphs.
    best: list[str] = []
    for box in soup.select(".transcript.storytext, .transcript, .storytext, #storytext"):
        for junk in box.select(NOT_BODY):
            junk.decompose()
        paras = [p.get_text(" ", strip=True) for p in box.find_all("p") if p.get_text(strip=True)]
        if len(paras) > len(best):
            best = paras
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only process the first N stories")
    ap.add_argument("--audio", action="store_true",
                    help="also download the mp3s (slow, but the links rot — the news site expires old audio)")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    args = ap.parse_args()

    urls_file = DATA / "urls.json"
    if not urls_file.exists():
        sys.exit(f"missing {urls_file} — run collect-urls.js in Chrome first")

    urls = json.loads(urls_file.read_text())
    if args.limit:
        urls = urls[: args.limit]

    for d in (RAW, TRANSCRIPTS, AUDIO, STORIES):
        d.mkdir(parents=True, exist_ok=True)

    total = len(urls)
    print(f"{total} stories to archive\n")
    stats = {"new": 0, "cached": 0, "failed": 0, "audio": 0, "transcripts": 0}

    for i, url in enumerate(urls, 1):
        sid = story_id(url)
        out = STORIES / f"{sid}.json"
        raw = RAW / f"{sid}.html"

        if out.exists():
            stats["cached"] += 1
            continue

        # Reuse cached HTML if we already pulled it on an earlier run.
        if raw.exists():
            html = raw.read_text(encoding="utf-8", errors="replace")
        else:
            r = get(url)
            if not r:
                stats["failed"] += 1
                print(f"[{i}/{total}] FAILED {url}")
                continue
            html = r.text
            raw.write_text(html, encoding="utf-8")
            time.sleep(args.delay)

        story = parse_story(html, url)
        label = (story["title"] or sid)[:58]
        print(f"[{i}/{total}] {story['date'][:10]}  {label}")

        if story["transcript_url"]:
            tfile = TRANSCRIPTS / f"{sid}.json"
            if tfile.exists():
                story["has_transcript"] = True
            else:
                r = get(story["transcript_url"])
                time.sleep(args.delay)
                if r:
                    paras = parse_transcript(r.text)
                    if paras:
                        tfile.write_text(json.dumps(paras, indent=2))
                        story["has_transcript"] = True
                        stats["transcripts"] += 1
                        print(f"      + transcript ({len(paras)} paras)")

        if story["audio_url"] and args.audio:
            mp3 = AUDIO / f"{sid}.mp3"
            if mp3.exists() and mp3.stat().st_size > 0:
                story["has_audio"] = True
            else:
                # the news site appends tracking params; the bare URL serves the same file.
                r = get(story["audio_url"].split("?")[0])
                time.sleep(args.delay)
                if r and r.content:
                    mp3.write_bytes(r.content)
                    story["has_audio"] = True
                    stats["audio"] += 1
                    print(f"      + audio ({len(r.content) // 1024} KB)")
                else:
                    print("      - audio expired / unavailable")

        out.write_text(json.dumps(story, indent=2, ensure_ascii=False))
        stats["new"] += 1

    print(
        f"\ndone — {stats['new']} new, {stats['cached']} already had, "
        f"{stats['failed']} failed | {stats['transcripts']} transcripts, "
        f"{stats['audio']} audio files"
    )


if __name__ == "__main__":
    main()
