"""Tests for build_site — the browsable local site builder.

Covers the two things that make the built page correct and offline-usable:
  * load() orders stories newest-first and picks the right audio source
    (a locally-saved mp3 wins over the site's remote URL); and
  * main() inlines the full story index into index.html so the page needs no
    network to render — the data lives in a <script> in the document itself.
"""

import json

import build_site


def _repoint(monkeypatch, tmp_path):
    stories = tmp_path / "stories"
    audio = tmp_path / "audio"
    site = tmp_path / "site"
    stories.mkdir()
    audio.mkdir()
    monkeypatch.setattr(build_site, "STORIES", stories)
    monkeypatch.setattr(build_site, "AUDIO", audio)
    monkeypatch.setattr(build_site, "SITE", site)
    return stories, audio, site


def test_load_orders_newest_first(monkeypatch, tmp_path, make_story):
    stories, _, _ = _repoint(monkeypatch, tmp_path)
    make_story(stories, "old", "2025-01-01T00:00:00", "Old story")
    make_story(stories, "mid", "2025-06-15T00:00:00", "Mid story")
    make_story(stories, "new", "2025-12-31T00:00:00", "New story")

    rows = build_site.load()

    assert [r["id"] for r in rows] == ["new", "mid", "old"]


def test_load_prefers_local_audio_over_remote(monkeypatch, tmp_path, make_story):
    stories, audio, _ = _repoint(monkeypatch, tmp_path)
    # Story with a locally-saved mp3: local copy must win.
    make_story(stories, "local", "2025-02-02T00:00:00", "Has local mp3",
               audio_url="https://cdn.example.com/remote.mp3")
    (audio / "local.mp3").write_bytes(b"fake-mp3-bytes")
    # Story with only the remote URL: falls back to that.
    make_story(stories, "remote", "2025-01-01T00:00:00", "Only remote",
               audio_url="https://cdn.example.com/only-remote.mp3")

    rows = {r["id"]: r for r in build_site.load()}

    assert rows["local"]["audio_is_local"] is True
    assert rows["local"]["audio"] == "../audio/local.mp3"
    assert rows["remote"]["audio_is_local"] is False
    assert rows["remote"]["audio"] == "https://cdn.example.com/only-remote.mp3"


def test_main_writes_single_self_contained_index(monkeypatch, tmp_path, make_story):
    stories, _, site = _repoint(monkeypatch, tmp_path)
    make_story(stories, "s1", "2025-05-05T00:00:00", "Findable Headline",
               paragraphs=["p"])

    build_site.main()

    index = site / "index.html"
    assert index.exists()
    page = index.read_text()
    # Styles and behaviour are inlined; the story index is embedded as data.
    assert "<style>" in page and "const STORIES" in page
    assert "Findable Headline" in page
    # The embedded data is valid JSON carrying the story we wrote.
    data = json.loads(page.split("const STORIES = ", 1)[1].split(";</script>", 1)[0])
    assert [s["id"] for s in data] == ["s1"]


def test_visible_render_path_escapes_titles(monkeypatch, tmp_path, make_story):
    # The client-side card() renderer escapes titles via esc() before writing
    # them into the DOM, so the escape helper the page ships must be present.
    stories, _, site = _repoint(monkeypatch, tmp_path)
    make_story(stories, "x", "2025-05-05T00:00:00", "Plain Title")

    build_site.main()
    page = (site / "index.html").read_text()

    # esc() maps &<>" to entities and is applied to every title/subtitle at render.
    assert "esc(s.title)" in page
    assert "'&':'&amp;','<':'&lt;','>':'&gt;'" in page


def test_inlined_data_block_does_not_neutralize_closing_script_tag(monkeypatch, tmp_path, make_story):
    # KNOWN BUG (documented, not fixed here — fixing would change app logic):
    # story metadata is inlined into a <script>const STORIES = ...</script>
    # block with json.dumps(..., ensure_ascii=False), which does NOT escape
    # "</script>". A title containing that literal substring would prematurely
    # close the data element and break the page. This test pins the CURRENT
    # behavior so the regression is visible if/when it is fixed.
    stories, _, site = _repoint(monkeypatch, tmp_path)
    make_story(stories, "x", "2025-05-05T00:00:00", "Danger </script> here")

    build_site.main()
    page = (site / "index.html").read_text()

    # Current behavior: the closing tag is emitted verbatim inside the data block.
    assert "Danger </script> here" in page


def test_main_raises_when_no_stories(monkeypatch, tmp_path):
    _repoint(monkeypatch, tmp_path)
    try:
        build_site.main()
    except SystemExit:
        return
    raise AssertionError("expected SystemExit when there are no stories")
