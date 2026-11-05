from flask import Blueprint, flash, redirect, render_template, url_for

from app import db
from app.services import archive, health, torrent
from app.services.qbittorrent import QbtError

bp = Blueprint("item", __name__)


@bp.get("/item/<path:identifier>")
def detail(identifier: str):
    error = None
    item = None
    try:
        item = archive.resolve(identifier)
    except archive.ArchiveError as exc:
        error = str(exc)

    settings = db.get_settings()
    return render_template(
        "item.html",
        identifier=identifier,
        item=item,
        error=error,
        settings=settings,
        download_dir_ready=bool(settings.get("download_dir")),
    )


@bp.post("/item/<path:identifier>/download")
def download(identifier: str):
    settings = db.get_settings()

    if not settings.get("download_dir"):
        flash(
            "Configure o diretório de downloads (caminho do host) antes de baixar.",
            "error",
        )
        return redirect(url_for("settings.edit"))

    status = health.check()
    if not status["ok"]:
        flash(f"qBittorrent indisponível: {status['error']}", "error")
        return redirect(url_for("item.detail", identifier=identifier))

    try:
        item = archive.resolve(identifier)
        if not item["available"]:
            raise archive.ArchiveError(item["reason"] or "Torrent indisponível.")

        data = archive.fetch_torrent(item["torrent_url"])
        info_hash = torrent.infohash(data)

        existing = db.find_by_hash(info_hash)
        if existing:
            flash(
                f"Este torrent já foi adicionado em {existing['added_at']} "
                f"(status: {existing['status']}).",
                "info",
            )
            return redirect(url_for("history.index"))

        client = health.client()
        try:
            client.create_category(settings.get("category", ""), settings.get("download_dir", ""))
        except QbtError:
            pass  # categoria já existe ou não pôde ser criada; o add decide

        client.add_torrent(
            data,
            item["torrent_name"] or f"{identifier}.torrent",
            savepath=settings.get("download_dir", ""),
            category=settings.get("category", ""),
            paused=settings.get("add_paused") == "1",
            tags="jelly-downloader",
        )

        db.add_download(
            identifier=identifier,
            title=item["title"],
            torrent_url=item["torrent_url"],
            info_hash=info_hash,
            category=settings.get("category", ""),
            savepath=settings.get("download_dir", ""),
            size=item["total_size"],
        )
    except (archive.ArchiveError, QbtError, torrent.BencodeError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("item.detail", identifier=identifier))

    flash(f'"{item["title"]}" foi enviado ao qBittorrent.', "success")
    return redirect(url_for("history.index"))
