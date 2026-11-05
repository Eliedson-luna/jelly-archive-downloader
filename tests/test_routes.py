from app import db
from app.services import archive


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Encontre um filme" in response.get_data(as_text=True)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["app"] == "ok"


def test_search_renders_results(client, monkeypatch):
    monkeypatch.setattr(
        archive,
        "search",
        lambda template, query, rows: [
            {
                "identifier": "abc",
                "title": "Night of the Living Dead",
                "year": "1968",
                "description": "Clássico",
                "downloads": 10,
                "details_url": "https://archive.org/details/abc",
            }
        ],
    )
    response = client.get("/search?q=nigth")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Night of the Living Dead" in body
    assert '/api/torrent-check/abc' in body


def test_search_reports_archive_error(client, monkeypatch):
    def boom(*args, **kwargs):
        raise archive.ArchiveError("falha simulada")

    monkeypatch.setattr(archive, "search", boom)
    response = client.get("/search?q=x")
    assert "falha simulada" in response.get_data(as_text=True)


def test_settings_requires_query_marker(client):
    response = client.post(
        "/settings",
        data={
            "qbittorrent_url": "http://127.0.0.1:8080",
            "qbittorrent_user": "admin",
            "category": "jelly",
            "download_dir": "/home/user/Downloads",
            "search_url": "https://archive.org/advancedsearch.php?q=test",
            "rows_per_page": "30",
            "request_timeout": "15",
        },
    )
    assert response.status_code == 200
    assert "{query}" in response.get_data(as_text=True)


def test_settings_saves_values(app, client):
    response = client.post(
        "/settings",
        data={
            "qbittorrent_url": "http://127.0.0.1:8080",
            "qbittorrent_user": "admin",
            "qbittorrent_password": "segredo",
            "category": "filmes",
            "download_dir": "/home/user/Downloads",
            "search_url": "https://archive.org/advancedsearch.php?q={query}",
            "rows_per_page": "20",
            "request_timeout": "10",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        settings = db.get_settings()
    assert settings["download_dir"] == "/home/user/Downloads"
    assert settings["category"] == "filmes"
    assert settings["qbittorrent_password"] == "segredo"


def test_settings_page_has_credentials_fields(client):
    body = client.get("/settings").get_data(as_text=True)
    assert 'name="qbittorrent_user"' in body
    assert 'name="qbittorrent_password"' in body
    assert 'data-toggle-password="qbittorrent_password"' in body
    assert "Testar conexão" in body


def test_settings_keeps_password_when_left_blank(app, client):
    with app.app_context():
        db.set_setting("qbittorrent_password", "senha-antiga")
        db.get_db().commit()

    client.post(
        "/settings",
        data={
            "qbittorrent_url": "http://127.0.0.1:8080",
            "qbittorrent_user": "novo-usuario",
            "qbittorrent_password": "",
            "category": "jelly",
            "download_dir": "/home/user/Downloads",
            "search_url": "https://archive.org/advancedsearch.php?q={query}",
            "rows_per_page": "30",
            "request_timeout": "15",
        },
    )

    with app.app_context():
        assert db.get_setting("qbittorrent_user") == "novo-usuario"
        assert db.get_setting("qbittorrent_password") == "senha-antiga"


def test_download_requires_download_dir(client):
    response = client.post("/item/abc/download")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")


def test_history_empty(client):
    response = client.get("/history")
    assert response.status_code == 200
    assert "Nenhum download ainda" in response.get_data(as_text=True)


def test_history_api_returns_rows(client):
    response = client.get("/api/history")
    assert response.status_code == 200
    assert "<tr>" in response.get_data(as_text=True)


def test_torrent_check_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        archive,
        "resolve",
        lambda identifier: {
            "available": True,
            "reason": "",
            "torrent_size": 4500,
            "total_size": 1024,
            "files": [1],
        },
    )
    payload = client.get("/api/torrent-check/abc").get_json()
    assert payload["available"] is True
    assert payload["total_size"] == 1024
