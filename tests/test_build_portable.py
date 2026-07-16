"""Tests for build_portable — the single-file, offline, sendable bundle.

The whole promise of this builder is a *self-contained* document: one HTML file
that opens forever offline, with story text and transcripts embedded directly
(browsers block a file:// page from fetching sidecar files). These tests assert
that promise holds: exactly one HTML file, styles/behaviour/text/transcripts all
inlined, newest-first ordering, and audio placed alongside as a relative link.
"""

import json
import sys

import build_portable


def _repoint(monkeypatch, tmp_path):
    stories = tmp_path / "stories"
    audio = tmp_path / "audio"
    transcripts = tmp_path / "transcripts"
    export = tmp_path / "export"
    bundle = export / "Story-Archive"
    for d in (stories, audio, transcripts):
        d.mkdir()
    monkeypatch.setattr(build_portable, "STORIES", stories)
    monkeypatch.setattr(build_portable, "AUDIO", audio)
    monkeypatch.setattr(build_portable, "TRANSCRIPTS", transcripts)
    monkeypatch.setattr(build_portable, "EXPORT", export)
    monkeypatch.setattr(build_portable, "BUNDLE", bundle)
    # main() reads argv via argparse; keep it clean of pytest's own flags.
    monkeypatch.setattr(sys, "argv", ["build_portable.py"])
    return stories, audio, transcripts, bundle


def _embedded(page):
    """Pull and parse the inlined STORIES data out of the built page."""
    raw = page.split("const STORIES=", 1)[1].rsplit(";</script>", 1)[0]
    return json.loads(raw)


def test_produces_exactly_one_html_file(monkeypatch, tmp_path, make_story):
    stories, _, _, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "s1", "2025-03-03T00:00:00", "A story", paragraphs=["body"])

    build_portable.main()

    htmls = list(bundle.glob("*.html"))
    assert len(htmls) == 1
    assert htmls[0].name == "Story Archive.html"


def test_document_is_self_contained(monkeypatch, tmp_path, make_story):
    # Styles and behaviour must be inline (no external <link>/<script src>),
    # so the file works with nothing beside it.
    stories, _, _, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "s1", "2025-03-03T00:00:00", "A story", paragraphs=["body"])

    build_portable.main()
    page = (bundle / "Story Archive.html").read_text()

    assert "<style>" in page and "<script>" in page
    # No external resource dependencies of any kind.
    assert "<link" not in page          # no external stylesheet
    assert "<script src" not in page    # no external script
    assert 'src="http' not in page      # no remotely-loaded asset src


def test_story_text_and_transcripts_are_embedded_inline(monkeypatch, tmp_path, make_story):
    # The defining feature: text and transcripts live *inside* the page, not in
    # sidecar files a file:// page could never fetch.
    stories, _, transcripts, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "s1", "2025-03-03T00:00:00", "Embedded story",
               paragraphs=["Paragraph one of the story.", "Paragraph two."],
               has_transcript=True)
    (transcripts / "s1.json").write_text(json.dumps(["Transcript line A.", "Transcript line B."]))

    build_portable.main()
    page = (bundle / "Story Archive.html").read_text()
    data = _embedded(page)

    assert len(data) == 1
    assert data[0]["text"] == ["Paragraph one of the story.", "Paragraph two."]
    assert data[0]["transcript"] == ["Transcript line A.", "Transcript line B."]
    # And they are physically present in the served bytes.
    assert "Paragraph two." in page and "Transcript line B." in page


def test_missing_transcript_yields_empty_list_not_error(monkeypatch, tmp_path, make_story):
    stories, _, _, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "s1", "2025-03-03T00:00:00", "No transcript", paragraphs=["x"])

    build_portable.main()
    data = _embedded((bundle / "Story Archive.html").read_text())

    assert data[0]["transcript"] == []


def test_stories_ordered_newest_first(monkeypatch, tmp_path, make_story):
    stories, _, _, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "old", "2024-01-01T00:00:00", "Old", paragraphs=["a"])
    make_story(stories, "new", "2025-12-31T00:00:00", "New", paragraphs=["b"])
    make_story(stories, "mid", "2025-05-05T00:00:00", "Mid", paragraphs=["c"])

    build_portable.main()
    data = _embedded((bundle / "Story Archive.html").read_text())

    assert [d["id"] for d in data] == ["new", "mid", "old"]


def test_audio_bundled_alongside_and_referenced_relatively(monkeypatch, tmp_path, make_story):
    # Non-empty audio is copied into the bundle's audio/ folder and referenced
    # by a relative path (so it plays offline next to the HTML). Stories with
    # no audio carry an empty audio field.
    stories, audio, _, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "hasaudio", "2025-02-02T00:00:00", "Has audio", paragraphs=["x"])
    make_story(stories, "noaudio", "2025-01-01T00:00:00", "No audio", paragraphs=["y"])
    (audio / "hasaudio.mp3").write_bytes(b"real-audio-bytes")

    build_portable.main()
    data = {d["id"]: d for d in _embedded((bundle / "Story Archive.html").read_text())}

    assert (bundle / "audio" / "hasaudio.mp3").exists()
    assert data["hasaudio"]["audio"] == "audio/hasaudio.mp3"
    assert data["noaudio"]["audio"] == ""


def test_empty_audio_file_is_not_bundled(monkeypatch, tmp_path, make_story):
    # A zero-byte mp3 (a failed/expired download) must not be treated as audio.
    stories, audio, _, bundle = _repoint(monkeypatch, tmp_path)
    make_story(stories, "s1", "2025-02-02T00:00:00", "Empty audio", paragraphs=["x"])
    (audio / "s1.mp3").write_bytes(b"")

    build_portable.main()
    data = _embedded((bundle / "Story Archive.html").read_text())

    assert data[0]["audio"] == ""
    assert not (bundle / "audio" / "s1.mp3").exists()
