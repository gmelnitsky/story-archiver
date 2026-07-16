"""Tests for scrape.parse_story / parse_transcript — the content-extraction core.

These run entirely on small inline HTML fixtures: no network, no live site,
no copyrighted content. They lock in the extraction rules the code comments
describe (prefer structured ld+json metadata, strip page furniture, dedupe
bylines, resolve the *named* transcript link rather than the bare nav one,
and pick the transcript container that actually holds the text).
"""

import scrape


STORY_HTML = """<html><head>
<script type="application/ld+json">
{"headline": "Structured Headline",
 "datePublished": "2025-10-24T09:00:00",
 "description": "A one-line teaser.",
 "author": {"name": "Jane Doe"}}
</script></head><body>
<h1>Fallback H1 Headline</h1>
<div class="slug-wrap"><a class="slug">Morning Edition</a></div>
<span class="byline__name">Jane Doe</span>
<span class="byline__name">Jane Doe</span>
<span class="byline__name"></span>
<span class="byline__name">Bob Roe</span>
<div id="storytext">
  <figure>photo caption furniture</figure>
  <aside>related links furniture</aside>
  <p>First real paragraph.</p>
  <p>Second paragraph has exactly five words.</p>
  <p>   </p>
</div>
<div data-audio='{"available": true, "audioUrl": "https://cdn.example.com/a.mp3?trk=1", "duration": 212}'></div>
<a href="/transcripts/">Transcripts</a>
<a href="/transcripts/nx-s1-5581432/some-story">Read the transcript</a>
</body></html>"""


def _story():
    return scrape.parse_story(STORY_HTML, "https://example.com/2025/10/24/nx-s1-5581432/x")


def test_title_prefers_structured_metadata_over_h1():
    assert _story()["title"] == "Structured Headline"


def test_title_falls_back_to_h1_without_structured_metadata():
    html = '<html><body><h1>Only An H1</h1><div id="storytext"><p>Body.</p></div></body></html>'
    assert scrape.parse_story(html, "https://x/2025/01/02/id9/z")["title"] == "Only An H1"


def test_byline_dedupes_preserving_order_and_drops_blanks():
    # Duplicate "Jane Doe" collapses to one, the empty name is dropped, and
    # first-seen order (Jane before Bob) is preserved.
    assert _story()["byline"] == ["Jane Doe", "Bob Roe"]


def test_teaser_show_and_date_come_from_structured_sources():
    s = _story()
    assert s["teaser"] == "A one-line teaser."
    assert s["show"] == "Morning Edition"
    assert s["date"] == "2025-10-24T09:00:00"


def test_paragraphs_strip_furniture_and_blank_nodes():
    # figure/aside are page furniture (NOT_BODY); the whitespace-only <p> is
    # dropped. Exactly the two real paragraphs survive, in order.
    assert _story()["paragraphs"] == [
        "First real paragraph.",
        "Second paragraph has exactly five words.",
    ]


def test_word_count_matches_extracted_paragraph_text():
    s = _story()
    # "First real paragraph." (3) + "Second paragraph has exactly five words." (6)
    assert s["word_count"] == sum(len(p.split()) for p in s["paragraphs"]) == 9


def test_audio_parsed_from_embedded_json_module():
    s = _story()
    assert s["audio_url"] == "https://cdn.example.com/a.mp3?trk=1"
    assert s["duration"] == 212


def test_transcript_link_must_name_a_story_and_is_absolutized():
    # The bare "/transcripts/" nav link is ignored; only the link that names a
    # story is taken, and it is resolved against the story URL to an absolute URL.
    assert _story()["transcript_url"] == "https://example.com/transcripts/nx-s1-5581432/some-story"


def test_bare_transcript_nav_link_alone_yields_no_transcript_url():
    html = '<html><body><div id="storytext"><p>x</p></div><a href="/transcripts/">Transcripts</a></body></html>'
    assert scrape.parse_story(html, "https://example.com/2025/10/24/id/x")["transcript_url"] == ""


def test_malformed_audio_json_is_swallowed_not_raised():
    # Resilience: broken data-audio must not crash extraction.
    html = '<html><body><div id="storytext"><p>x</p></div><div data-audio="{not json}"></div></body></html>'
    s = scrape.parse_story(html, "https://example.com/2025/10/24/id/x")
    assert s["audio_url"] == "" and s["duration"] is None


TRANSCRIPT_HTML = """<html><body>
<div class="transcript"></div>
<div class="transcript storytext">
  <p>Transcript line one.</p>
  <p>Transcript line two.</p>
  <p>Transcript line three.</p>
</div>
</body></html>"""


def test_transcript_picks_the_fullest_candidate_container():
    # An empty ".transcript" wrapper sits earlier in the document than the real
    # one; document-order selection would grab the empty box. parse_transcript
    # instead returns whichever candidate holds the most paragraphs.
    assert scrape.parse_transcript(TRANSCRIPT_HTML) == [
        "Transcript line one.",
        "Transcript line two.",
        "Transcript line three.",
    ]
