import pytest

from app.services.qbittorrent import QBittorrentClient, QbtError, map_status


class FakeResponse:
    def __init__(self, status=200, text="Ok.", payload=None):
        self.status_code = status
        self.text = text
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("sem json")
        return self._payload


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.headers = {}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.handler("POST", url, kwargs)

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.handler(method, url, kwargs)


def make_client(version=None):
    client = QBittorrentClient("http://127.0.0.1:8080", "admin", "senha")
    if version:
        client._version = version
    return client


def test_login_ok():
    client = make_client()
    client.session = FakeSession(lambda m, u, k: FakeResponse(200, "Ok."))
    client.login()
    assert client._logged_in is True
    assert client.session.calls[0][1].endswith("/api/v2/auth/login")


def test_login_rejected():
    client = make_client()
    client.session = FakeSession(lambda m, u, k: FakeResponse(403, "Fails."))
    with pytest.raises(QbtError):
        client.login()


def test_login_bad_credentials():
    client = make_client()
    client.session = FakeSession(lambda m, u, k: FakeResponse(200, "Fails."))
    with pytest.raises(QbtError):
        client.login()


def test_add_torrent_uses_paused_on_v4():
    client = make_client("v4.6.2")
    seen = {}

    def handler(method, url, kwargs):
        seen.update(kwargs)
        return FakeResponse(200, "Ok.")

    client.session = FakeSession(handler)
    client.add_torrent(b"d4:infoe", "x.torrent", "/downloads", "jelly", paused=True)
    assert seen["data"]["paused"] == "true"
    assert "stopped" not in seen["data"]
    assert seen["files"]["torrents"][0] == "x.torrent"


def test_add_torrent_uses_stopped_on_v5():
    client = make_client("v5.0.3")
    seen = {}

    def handler(method, url, kwargs):
        seen.update(kwargs)
        return FakeResponse(200, "Ok.")

    client.session = FakeSession(handler)
    client.add_torrent(b"d4:infoe", "x.torrent", "/downloads", paused=False)
    assert seen["data"]["stopped"] == "false"
    assert "paused" not in seen["data"]


def test_add_torrent_detects_failure():
    client = make_client("v4.6.2")
    client.session = FakeSession(lambda m, u, k: FakeResponse(200, "Fails."))
    with pytest.raises(QbtError):
        client.add_torrent(b"d4:infoe", "x.torrent", "/downloads")


def test_torrents_info_returns_list():
    client = make_client("v4.6.2")
    payload = [{"hash": "abc", "progress": 0.5, "state": "downloading", "size": 10}]
    client.session = FakeSession(lambda m, u, k: FakeResponse(payload=payload))
    assert client.torrents_info() == payload


def test_map_status():
    assert map_status({"progress": 1.0, "state": "uploading"})[0] == "completed"
    assert map_status({"progress": 0.2, "state": "downloading"})[0] == "downloading"
    assert map_status({"progress": 0.2, "state": "stalledDL"})[0] == "stalled"
    assert map_status({"progress": 0.0, "state": "pausedDL"})[0] == "paused"
    assert map_status({"progress": 0.0, "state": "queuedDL"})[0] == "queued"
    assert map_status({"progress": 0.0, "state": "error"})[0] == "error"
    assert map_status({"progress": 0.0, "state": "missingFiles"})[0] == "error"
