import pytest

from app.services import archive


def test_build_search_url_replaces_query_and_rows():
    url = archive.build_search_url(
        "https://archive.org/advancedsearch.php?q={query}&rows={rows}&output=json",
        "Death Note",
        25,
    )
    assert "q=Death+Note" in url
    assert "rows=25" in url


def test_build_search_url_requires_marker():
    with pytest.raises(archive.ArchiveError):
        archive.build_search_url("https://example.com/search?term=x", "abc", 10)


def test_sanitize_query_removes_syntax():
    assert archive.sanitize_query("  Night  of (the) Living Dead ") == "Night of the Living Dead"
    assert archive.sanitize_query('a:b "c"') == "a b c"
    assert archive.sanitize_query("x" * 300) == "x" * 200
    assert archive.sanitize_query("") == ""


def test_clean_text_strips_html_and_limits():
    text = archive.clean_text("<p>Olá <b>mundo</b></p>", limit=100)
    assert text == "Olá mundo"
    long = archive.clean_text("a" * 200, limit=50)
    assert len(long) == 50 and long.endswith("…")


def test_normalize_doc_handles_missing_fields():
    item = archive.normalize_doc({"identifier": "abc", "title": "<b>Filme</b>", "year": 1999})
    assert item["identifier"] == "abc"
    assert item["title"] == "Filme"
    assert item["year"] == "1999"
    assert item["downloads"] == 0
    assert item["details_url"].endswith("/details/abc")


def test_extract_docs_supports_known_shapes():
    docs = [{"identifier": "a"}]
    assert archive._extract_docs({"response": {"docs": docs}}) == docs
    assert archive._extract_docs({"items": docs}) == docs
    assert archive._extract_docs({"docs": docs}) == docs
    assert archive._extract_docs(docs) == docs
    assert archive._extract_docs({"foo": 1}) == []


def test_search_parses_json(app, monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"response": {"docs": [{"identifier": "x", "title": "T", "downloads": 3}]}}

    monkeypatch.setattr(archive.requests, "get", lambda *a, **k: Response())
    with app.app_context():
        results = archive.search("https://x/?q={query}&rows={rows}", "abc", 10)
    assert results[0]["identifier"] == "x"
    assert results[0]["downloads"] == 3


def test_search_reports_non_json(app, monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            raise ValueError("não é json")

    monkeypatch.setattr(archive.requests, "get", lambda *a, **k: Response())
    with app.app_context(), pytest.raises(archive.ArchiveError):
        archive.search("https://x/?q={query}", "abc", 10)


def _fake_meta(**overrides):
    meta = {
        "metadata": {"title": "Filme", "description": "<b>Sinopse</b>", "year": "1968"},
        "files": [
            {"name": "Filme_archive.torrent", "format": "Archive BitTorrent", "size": "4500"},
            {"name": "Filme.mp4", "format": "MPEG4", "size": "1048576"},
        ],
        "item_size": "1048576",
        "d1": "ia801.us.archive.org",
    }
    meta.update(overrides)
    return meta


def test_resolve_available_item(monkeypatch):
    monkeypatch.setattr(archive, "get_metadata", lambda identifier: _fake_meta())
    item = archive.resolve("filme")
    assert item["available"] is True
    assert item["torrent_url"] == "https://archive.org/download/filme/Filme_archive.torrent"
    assert item["total_size"] == 1048576
    assert item["description"] == "Sinopse"


def test_resolve_dark_item(monkeypatch):
    monkeypatch.setattr(archive, "get_metadata", lambda identifier: _fake_meta(is_dark=True))
    item = archive.resolve("filme")
    assert item["available"] is False
    assert "escuro" in item["reason"]


def test_resolve_uses_fallback_listing(monkeypatch):
    meta = _fake_meta(files=[{"name": "Filme.mp4", "format": "MPEG4", "size": "10"}])
    monkeypatch.setattr(archive, "get_metadata", lambda identifier: meta)
    monkeypatch.setattr(
        archive,
        "_fallback_torrent_url",
        lambda identifier: ("fallback.torrent", "https://archive.org/download/filme/fallback.torrent"),
    )
    item = archive.resolve("filme")
    assert item["available"] is True
    assert item["torrent_url"].endswith("fallback.torrent")


def test_resolve_without_torrent(monkeypatch):
    meta = _fake_meta(files=[{"name": "Filme.mp4", "format": "MPEG4", "size": "10"}])
    monkeypatch.setattr(archive, "get_metadata", lambda identifier: meta)
    monkeypatch.setattr(archive, "_fallback_torrent_url", lambda identifier: None)
    item = archive.resolve("filme")
    assert item["available"] is False
    assert "torrent" in item["reason"].lower()
