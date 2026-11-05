from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app import db
from app.services import health

bp = Blueprint("settings", __name__)

EDITABLE = (
    "qbittorrent_url",
    "qbittorrent_user",
    "category",
    "download_dir",
    "add_paused",
    "search_url",
    "rows_per_page",
    "request_timeout",
)


def _form_values(settings: dict) -> dict:
    values = {key: settings.get(key, "") for key in EDITABLE}
    values["qbittorrent_password"] = ""
    return values


@bp.get("/settings")
def edit():
    settings = db.get_settings()
    return render_template(
        "settings.html",
        values=_form_values(settings),
        env_keys=db.env_managed_keys(),
        status=health.check(),
        has_password=bool(settings.get("qbittorrent_password")),
        saved=False,
    )


@bp.post("/settings")
def save():
    form = {key: (request.form.get(key) or "").strip() for key in EDITABLE}
    form["add_paused"] = "1" if request.form.get("add_paused") else "0"
    password = (request.form.get("qbittorrent_password") or "").strip()

    errors = []
    if not form["qbittorrent_url"].startswith(("http://", "https://")):
        errors.append("A URL do qBittorrent deve começar com http:// ou https://.")
    if "{query}" not in form["search_url"]:
        errors.append("A URL de busca precisa conter o marcador {query}.")
    if form["download_dir"] and not form["download_dir"].startswith("/"):
        errors.append("O diretório de downloads deve ser um caminho absoluto do host.")

    try:
        rows = int(form["rows_per_page"])
        if rows < 1:
            raise ValueError
        form["rows_per_page"] = str(min(rows, 50))
    except ValueError:
        errors.append("Resultados por página deve ser um número inteiro positivo.")

    try:
        timeout = int(form["request_timeout"])
        if timeout < 3:
            raise ValueError
        form["request_timeout"] = str(timeout)
    except ValueError:
        errors.append("Timeout deve ser um número inteiro maior ou igual a 3.")

    if errors:
        for message in errors:
            flash(message, "error")
        return render_template(
            "settings.html",
            values=form,
            env_keys=db.env_managed_keys(),
            status=health.check(),
            has_password=bool(db.get_setting("qbittorrent_password")),
            saved=False,
        )

    managed = db.env_managed_keys()
    for key, value in form.items():
        if key in managed:
            continue
        db.set_setting(key, value)

    if password and "qbittorrent_password" not in managed:
        db.set_setting("qbittorrent_password", password)

    db.get_db().commit()
    health.invalidate()
    flash("Configurações salvas.", "success")
    return redirect(url_for("settings.edit"))


def _submitted_connection_settings() -> tuple[dict | None, str | None]:
    """Monta uma configuração de teste a partir do formulário, sem salvar.

    Senha vazia usa a senha salva apenas quando a URL não mudou. Isso evita
    enviar a credencial antiga para um host novo.
    """
    saved = db.get_settings()
    submitted = {
        key: (request.form.get(key) or "").strip()
        for key in ("qbittorrent_url", "qbittorrent_user", "qbittorrent_password")
    }
    url = submitted["qbittorrent_url"] or saved.get("qbittorrent_url", "")
    user = submitted["qbittorrent_user"] or saved.get("qbittorrent_user", "")
    password = submitted["qbittorrent_password"]

    if not password:
        if url.rstrip("/") != (saved.get("qbittorrent_url") or "").rstrip("/"):
            return None, "Informe a senha para testar uma URL diferente da salva."
        password = saved.get("qbittorrent_password", "")

    return {
        "qbittorrent_url": url,
        "qbittorrent_user": user,
        "qbittorrent_password": password,
    }, None


@bp.post("/api/test-connection")
def test_connection():
    settings, error = _submitted_connection_settings()
    if error:
        return jsonify({"ok": False, "version": None, "error": error, "checked_at": ""})
    return jsonify(health.probe(settings))
