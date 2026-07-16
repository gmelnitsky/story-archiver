"""Tests for scrape.story_id — the stable identifier / safe-filename derivation.

story_id turns a story URL into the slug used for every on-disk artifact
(raw HTML, parsed JSON, transcript, audio). Two invariants matter:

  * it must be *stable* — the same story must always map to the same id,
    regardless of the trailing human-readable slug, or the resume logic
    (which skips work when ``<id>.json`` already exists) breaks; and
  * it must always be a *safe, bounded filename* even when the URL has no
    recognizable dated path, so nothing ever explodes into an unusable name.
"""

import scrape


def test_extracts_id_from_dated_path():
    # .../YYYY/MM/DD/<id>/<human-slug> -> the segment three past the year.
    url = "https://example.com/2025/10/24/nx-s1-5581432/boston-bar-closes"
    assert scrape.story_id(url) == "nx-s1-5581432"


def test_id_is_stable_across_trailing_slug():
    # The same story is stable whether or not it carries a trailing slug or
    # slash — this is what makes the scraper's "skip if already saved" resume
    # logic correct.
    a = scrape.story_id("https://example.com/2025/10/24/nx-s1-5581432/boston-bar")
    b = scrape.story_id("https://example.com/2025/10/24/nx-s1-5581432/boston-bar/")
    c = scrape.story_id("https://example.com/2025/10/24/nx-s1-5581432")
    assert a == b == c == "nx-s1-5581432"


def test_extraction_is_position_based_not_domain_based():
    # The id is the 4th segment after the year, independent of host.
    assert scrape.story_id("https://other.org/2019/03/07/abc-123/headline") == "abc-123"


def test_falls_back_when_no_dated_path():
    # No YYYY/MM/DD/<id> structure -> deterministic sanitized fallback.
    got = scrape.story_id("https://example.com/about/contact-us")
    assert got == "https-example-com-about-contact-us"


def test_fallback_replaces_non_word_runs_with_single_dash():
    # Every non-word run collapses to one dash — safe for a filename.
    got = scrape.story_id("https://x.com/a//b??c")
    assert " " not in got and "/" not in got and "?" not in got
    assert "--" not in got  # \W+ collapses runs, never doubles the dash


def test_fallback_is_bounded_to_40_chars():
    # A pathological URL must still yield a bounded filename.
    got = scrape.story_id("https://example.com/" + "x" * 200)
    assert len(got) <= 40


def test_dated_path_needs_enough_trailing_segments():
    # A year segment without the full /MM/DD/<id> tail must not IndexError;
    # it falls through to the sanitized fallback instead.
    got = scrape.story_id("https://example.com/2025/10/24")
    assert got == "https-example-com-2025-10-24"
