"""Fluxo completo contra um qBittorrent falso (HTTP real, em thread)."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import db
from app.services import archive, health, torrent
from tests.test_torrent import make_torrent


class StubQbt:
    def __init__(self):
        self.torrents = []
        self.added = []
        self.deleted = []
        handler = self._handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def _handler(self):
        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # silencia o log
                pass

            def _send(self, body=b"Ok.", code=200, ctype="text/plain"):
                if isinstance(body, str):
                    body = body.encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                if self.path.endswith("/auth/login"):
                    self.send_header("Set-Cookie", "SID=stub; path=/")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)

                if self.path.endswith("/auth/login"):
                    return self._send(b"Ok.")

                if self.path.endswith("/torrents/add"):
                    text = body.decode("latin1")
                    fields = {}
                    for key in ("savepath", "category", "tags", "paused", "stopped"):
                        match = re.search(rf'name="{key}"\r\n\r\n([^\r]*)\r\n', text)
                        if match:
                            fields[key] = match.group(1)
                    stub.added.append(fields)
                    return self._send(b"Ok.")

                if self.path.endswith("/torrents/delete"):
                    stub.deleted.append(body.decode())
                    return self._send(b"Ok.")

                if self.path.endswith("/createCategory"):
                    return self._send(b"Ok.")

                return self._send(b"Ok.")

            def do_GET(self):
                if self.path.endswith("/app/version"):
                    return self._send(b"v4.6.2")
                if "/torrents/info" in self.path:
                    payload = json.dumps(stub.torrents)
                    return self._send(payload, ctype="application/json")
                return self._send(b"Ok.")

        return Handler


@pytest.fixture
def stub_qbt():
    stub = StubQbt()
    yield stub
    stub.close()


@pytest.fixture
def configured_app(real_app, stub_qbt):
    with real_app.app_context():
        db.set_setting("qbittorrent_url", stub_qbt.url)
        db.set_setting("qbittorrent_user", "admin")
        db.set_setting("qbittorrent_password", "senha")
        db.set_setting("download_dir", "/home/user/Downloads")
        db.set_setting("category", "jelly")
        db.get_db().commit()
    health.invalidate()
    return real_app


def test_add_download_end_to_end(configured_app, stub_qbt, monkeypatch):
    torrent_bytes = make_torrent()
    expected_hash = torrent.infohash(torrent_bytes)

    monkeypatch.setattr(
        archive,
        "resolve",
        lambda identifier: {
            "identifier": identifier,
            "title": "Filme Teste",
            "available": True,
            "reason": "",
            "torrent_name": "filme_archive.torrent",
            "torrent_url": "https://example.invalid/filme_archive.torrent",
            "total_size": 4242,
            "files": [],
        },
    )
    monkeypatch.setattr(archive, "fetch_torrent", lambda url: torrent_bytes)

    client = configured_app.test_client()
    response = client.post("/item/filme/download")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/history")

    assert stub_qbt.added, "o torrent deveria ter sido enviado ao qBittorrent"
    assert stub_qbt.added[0]["savepath"] == "/home/user/Downloads"
    assert stub_qbt.added[0]["category"] == "jelly"

    with configured_app.app_context():
        rows = db.list_downloads()
    assert len(rows) == 1
    assert rows[0]["info_hash"] == expected_hash
    assert rows[0]["size"] == 4242

    # Simula o item aparecendo no qBittorrent e confere o histórico ao vivo.
    stub_qbt.torrents = [
        {
            "hash": expected_hash,
            "progress": 0.5,
            "state": "downloading",
            "size": 4242,
            "dlspeed": 2048,
            "eta": 120,
        }
    ]
    body = client.get("/api/history").get_data(as_text=True)
    assert "50.0%" in body
    assert "Baixando" in body

    with configured_app.app_context():
        assert db.list_downloads()[0]["status"] == "downloading"


def test_remove_download(configured_app, stub_qbt, monkeypatch):
    with configured_app.app_context():
        download_id = db.add_download(
            identifier="filme",
            title="Filme Teste",
            torrent_url="https://example.invalid/filme_archive.torrent",
            info_hash="a" * 40,
            category="jelly",
            savepath="/home/user/Downloads",
        )

    client = configured_app.test_client()
    response = client.post(f"/history/{download_id}/remove")
    assert response.status_code == 302
    assert stub_qbt.deleted, "o torrent deveria ter sido removido do qBittorrent"

    with configured_app.app_context():
        assert db.get_download(download_id)["status"] == "removed"


def test_history_marks_missing_when_not_in_qbt(configured_app, monkeypatch):
    with configured_app.app_context():
        db.add_download(
            identifier="filme",
            title="Filme",
            torrent_url="https://example.invalid/x.torrent",
            info_hash="b" * 40,
            category="jelly",
            savepath="/tmp",
        )

    client = configured_app.test_client()
    body = client.get("/api/history").get_data(as_text=True)
    assert "Fora do qBittorrent" in body

    with configured_app.app_context():
        assert db.list_downloads()[0]["status"] == "missing"


def test_health_detects_stub(configured_app, stub_qbt):
    with configured_app.app_context():
        status = health.check(force=True)
    assert status["ok"] is True
    assert status["version"] == "v4.6.2"
