"""Fábrica da aplicação Flask."""

from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from app import db
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


def human_date(value) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return str(value)
    return parsed.strftime("%d/%m/%Y %H:%M")


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
