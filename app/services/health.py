"""Checagem de disponibilidade do qBittorrent (com cache curto).

Essa é a verificação exigida no AGENTS.md: o container não possui o
qBittorrent, então o "software presente no sistema" é detectado pela Web UI
do qBittorrent que roda no host.
"""

import time
from datetime import datetime, timezone

from app import db
from app.services.qbittorrent import QBittorrentClient, QbtError, client_from_settings

_cache = {"at": 0.0, "status": None}


def _empty(error: str = "") -> dict:
    return {
        "ok": False,
        "version": None,
        "error": error or "qBittorrent não detectado.",
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def probe(settings: dict) -> dict:
    """Testa uma configuração sem alterar o cache global."""
    client = client_from_settings(settings)
    try:
        version = client.version()
        return {
            "ok": True,
            "version": version,
            "error": None,
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except QbtError as exc:
        return _empty(str(exc))
    except Exception as exc:  # nunca derrubar a página por causa do health
        return _empty(f"Erro inesperado ao falar com o qBittorrent: {exc}")


def check(force: bool = False) -> dict:
    from flask import current_app

    ttl = int(current_app.config["HEALTH_TTL"])
    now = time.monotonic()
    if not force and _cache["status"] and (now - _cache["at"]) < ttl:
        return _cache["status"]

    status = probe(db.get_settings())
    _cache["at"] = now
    _cache["status"] = status
    return status


def invalidate() -> None:
    _cache["at"] = 0.0
    _cache["status"] = None


def cached() -> dict | None:
    """Último resultado conhecido, sem disparar requisição."""
    return _cache["status"]


def client() -> QBittorrentClient:
    return client_from_settings(db.get_settings())
