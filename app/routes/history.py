from flask import Blueprint, flash, redirect, render_template, url_for

from app import db
from app.services import archive, health, torrent
from app.services.qbittorrent import QbtError, map_status

bp = Blueprint("history", __name__)


def _sync(rows: list) -> list:
    """Atualiza status/progresso local a partir do qBittorrent."""
    hashes = [row["info_hash"].lower() for row in rows if row["info_hash"]]
    if not hashes:
        return rows

    try:
        info = health.client().info_by_hash()
    except QbtError:
        for row in rows:
            row["live"] = False
        return rows

    for row in rows:
        row["live"] = False
        key = (row.get("info_hash") or "").lower()
        data = info.get(key)
        if not data:
            if row["status"] in {"added", "downloading", "queued", "paused", "stalled"}:
                row["status"] = "missing"
                db.update_download(row["id"], status="missing")
            continue

        status, progress = map_status(data)
        progress_pct = round(progress * 100, 1)

        old_status = row["status"]
        old_progress = float(row.get("progress") or 0)

        row["live"] = True
        row["progress"] = progress_pct
        row["status"] = status
        row["dlspeed"] = int(data.get("dlspeed") or 0)
        row["total_size"] = int(data.get("size") or row.get("size") or 0)
        row["eta"] = int(data.get("eta") or 0)

        if status != old_status or abs(progress_pct - old_progress) >= 0.1:
            db.update_download(
                row["id"],
                status=status,
                progress=progress_pct,
                size=row["total_size"] or row["size"],
            )
    return rows


def _rows():
    rows = db.list_downloads()
    for row in rows:
        row.setdefault("dlspeed", 0)
        row.setdefault("eta", 0)
        row.setdefault("total_size", row.get("size") or 0)
        row.setdefault("live", False)
    return _sync(rows)


@bp.get("/history")
def index():
    return render_template("history.html", rows=_rows())


@bp.get("/api/history")
def api_rows():
    return render_template("partials/history_rows.html", rows=_rows())


@bp.post("/history/<int:download_id>/remove")
def remove(download_id: int):
    row = db.get_download(download_id)
    if not row:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("history.index"))

    if row.get("info_hash"):
        try:
            health.client().delete([row["info_hash"]], delete_files=False)
        except QbtError as exc:
            flash(f"Falha ao remover do qBittorrent: {exc}", "error")
            return redirect(url_for("history.index"))

    db.update_download(download_id, status="removed")
    flash("Torrent removido do qBittorrent (arquivos mantidos).", "success")
    return redirect(url_for("history.index"))


@bp.post("/history/<int:download_id>/retry")
def retry(download_id: int):
    row = db.get_download(download_id)
    if not row:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("history.index"))

    settings = db.get_settings()
    if not settings.get("download_dir"):
        flash("Configure o diretório de downloads antes de reenviar.", "error")
        return redirect(url_for("settings.edit"))

    status = health.check()
    if not status["ok"]:
        flash(f"qBittorrent indisponível: {status['error']}", "error")
        return redirect(url_for("history.index"))

    try:
        data = archive.fetch_torrent(row["torrent_url"])
        info_hash = torrent.infohash(data)
        health.client().add_torrent(
            data,
            f"{row['identifier']}.torrent",
            savepath=row.get("savepath") or settings.get("download_dir", ""),
            category=row.get("category") or settings.get("category", ""),
            paused=settings.get("add_paused") == "1",
            tags="jelly-archive-downloader",
        )
    except (archive.ArchiveError, QbtError, torrent.BencodeError) as exc:
        db.update_download(download_id, status="error", last_error=str(exc))
        flash(str(exc), "error")
        return redirect(url_for("history.index"))

    db.update_download(download_id, status="added", info_hash=info_hash, last_error=None)
    flash("Torrent reenviado ao qBittorrent.", "success")
    return redirect(url_for("history.index"))
