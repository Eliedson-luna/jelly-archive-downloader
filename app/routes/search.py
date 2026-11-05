from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from app import db
from app.services import archive

bp = Blueprint("search", __name__)


def _rows(settings: dict) -> int:
    try:
        value = int(settings.get("rows_per_page") or 30)
    except (TypeError, ValueError):
        value = 30
    return max(1, min(value, current_app.config["MAX_ROWS"]))


@bp.get("/")
def index():
    return render_template(
        "search.html",
        query="",
        results=None,
        error=None,
        settings=db.get_settings(),
    )


@bp.get("/search")
def search():
    query = (request.args.get("q") or "").strip()
    settings = db.get_settings()

    if not query:
        return redirect(url_for("search.index"))

    results = []
    error = None
    try:
        results = archive.search(settings.get("search_url", ""), query, _rows(settings))
    except archive.ArchiveError as exc:
        error = str(exc)

    return render_template(
        "search.html",
        query=query,
        results=results,
        error=error,
        settings=settings,
    )


@bp.get("/api/torrent-check/<path:identifier>")
def torrent_check(identifier: str):
    """Usado pela interface para mostrar o selo de disponibilidade dos cards."""
    try:
        item = archive.resolve(identifier)
    except archive.ArchiveError as exc:
        return jsonify({"ok": False, "available": False, "reason": str(exc)}), 200

    return jsonify(
        {
            "ok": True,
            "available": item["available"],
            "reason": item["reason"],
            "torrent_size": item["torrent_size"],
            "total_size": item["total_size"],
            "files": len(item["files"]),
        }
    )
