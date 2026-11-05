import re

from app import human_date

SETTINGS = {
    "qbittorrent_url": "http://127.0.0.1:8080",
    "qbittorrent_user": "admin",
    "category": "jelly",
    "download_dir": "/home/user/Downloads",
    "search_url": "https://archive.org/advancedsearch.php?q={query}",
    "rows_per_page": "30",
    "request_timeout": "15",
}


def _token(client):
    body = client.get("/").get_data(as_text=True)
    match = re.search(r'name="csrf-token" content="([^"]+)"', body)
    assert match, "meta csrf-token ausente"
    return match.group(1)


def test_post_without_csrf_is_rejected(csrf_client):
    response = csrf_client.post("/settings", data=SETTINGS)
    assert response.status_code == 400
    assert "CSRF" in response.get_data(as_text=True)


def test_post_with_csrf_form_field_is_accepted(csrf_client):
    token = _token(csrf_client)
    response = csrf_client.post("/settings", data={**SETTINGS, "_csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")


def test_api_post_without_csrf_is_rejected(csrf_client):
    response = csrf_client.post("/api/test-connection")
    assert response.status_code == 400


def test_api_post_accepts_csrf_header(csrf_client):
    token = _token(csrf_client)
    response = csrf_client.post(
        "/api/test-connection", headers={"X-CSRF-Token": token}
    )
    assert response.status_code == 200
    assert response.get_json()["ok"] is False


def test_human_date_uses_configured_timezone(app):
    with app.app_context():
        app.config["TIMEZONE"] = "America/Sao_Paulo"
        assert human_date("2026-11-05T12:00:00Z") == "05/11/2026 09:00"


def test_human_date_falls_back_for_invalid_timezone(app):
    with app.app_context():
        app.config["TIMEZONE"] = "Fuso/Invalido"
        assert human_date("2026-11-05T12:00:00Z") == "05/11/2026 12:00"
