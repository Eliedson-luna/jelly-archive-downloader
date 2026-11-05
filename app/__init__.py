"""Fábrica da aplicação Flask."""

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, current_app, jsonify, render_template, request

from app import csrf, db
from app.config import Config
from app.services import health

STATUS_LABELS = {
    "added": "Adicionado",
    "downloading": "Baixando",
    "queued": "Na fila",
    "stalled": "Sem peers",
    "paused": "Pausado",
    "completed": "Concluído",
    "error": "Erro",
    "missing": "Fora do qBittorrent",
    "removed": "Removido",
}


def human_size(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number <= 0:
        return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while number >= 1024 and index < len(units) - 1:
        number /= 1024
        index += 1
    if index == 0:
        return f"{int(number)} B"
    return f"{number:.1f} {units[index]}"


def _load_secret_key(data_dir) -> str:
    """Carrega ou cria um segredo persistente para sessões/CSRF."""
    path = Path(data_dir) / "secret_key"
    try:
        if path.exists():
            stored = path.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        generated = secrets.token_hex(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return generated
    except OSError:
        # Último recurso: segredo volátil; sessões não sobrevivem a um restart.
        return secrets.token_hex(32)


def _display_timezone():
    try:
        name = current_app.config.get("TIMEZONE") or "UTC"
    except RuntimeError:
        name = os.environ.get("TZ", "UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def human_date(value) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return str(value)
    return parsed.astimezone(_display_timezone()).strftime("%d/%m/%Y %H:%M")


def human_eta(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if seconds <= 0 or seconds > 86400 * 7:
        return "—"
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}min"
    return f"{minutes}min"


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _load_secret_key(app.config["DATA_DIR"])
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

    app.before_request(csrf.protect)

    db.init_app(app)

    from app.routes import history, item, search, settings

    app.register_blueprint(search.bp)
    app.register_blueprint(item.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(settings.bp)

    app.jinja_env.filters["human_size"] = human_size
    app.jinja_env.filters["human_date"] = human_date
    app.jinja_env.filters["human_eta"] = human_eta

    @app.context_processor
    def inject_globals():
        status = {"ok": False, "version": None, "error": "Verificando..."}
        if request.endpoint not in {"health", "static"}:
            status = health.check()
        return {
            "app_name": "Jelly Archive Downloader",
            "qbt": status,
            "status_labels": STATUS_LABELS,
            "csrf_token": csrf.token,
        }

    @app.get("/health")
    def health_endpoint():
        # Não consulta o qBittorrent aqui: o healthcheck do container deve
        # medir apenas a aplicação (evita restart por causa do host).
        status = health.cached() or {
            "ok": False,
            "version": None,
            "error": "ainda não verificado",
        }
        return jsonify(
            {
                "app": "ok",
                "qbittorrent": status,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

    @app.errorhandler(400)
    def bad_request(error):
        message = getattr(error, "description", None) or "Requisição inválida."
        return render_template("error.html", code=400, message=message), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Página não encontrada."), 404

    @app.errorhandler(500)
    def server_error(_error):
        return (
            render_template(
                "error.html", code=500, message="Erro interno. Veja os logs do container."
            ),
            500,
        )

    return app
