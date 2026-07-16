"""Shared fixtures for the builder tests.

Both builders read their inputs from module-level directory globals and write
into module-level output globals. The fixtures below stand up a throwaway
directory tree of tiny JSON fixtures (never real, copyrighted content) and
repoint those globals at it, so the builders run fully offline against known
data. monkeypatch restores every global after each test.
"""

import json

import pytest


def _write_story(stories_dir, sid, date, title, *, teaser="Teaser.", show="Show",
                 paragraphs=None, audio_url="", duration=100, has_transcript=False,
                 url=None):
    paragraphs = paragraphs or []
    (stories_dir / f"{sid}.json").write_text(json.dumps({
        "id": sid,
        "title": title,
        "teaser": teaser,
        "date": date,
        "show": show,
        "byline": ["A. Reporter"],
        "url": url or f"https://example.com/story/{sid}",
        "audio_url": audio_url,
        "duration": duration,
        "has_transcript": has_transcript,
        "word_count": len(paragraphs),
        "paragraphs": paragraphs,
    }))


@pytest.fixture
def make_story():
    """Return a helper that writes a story JSON into a given stories dir."""
    return _write_story
