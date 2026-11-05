"""Configuração base da aplicação.

Valores sensíveis/operacionais podem ser sobrescritos por variáveis de
ambiente (ver ENV_MANAGED). Variáveis vazias são ignoradas para não apagar
configurações feitas pela interface web.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # Vazio significa: usar SECRET_KEY do ambiente ou gerar/persistir em DATA_DIR.
    SECRET_KEY = os.environ.get("SECRET_KEY") or ""

    DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
    DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "app.db"))

    # Proteção CSRF para todos os POSTs (desativada apenas em testes isolados).
    CSRF_ENABLED = True

    # Fuso usado para exibir datas do histórico (o banco continua em UTC).
    TIMEZONE = os.environ.get("TZ", "UTC")

    # Tempo de vida do cache de metadados do archive.org (segundos).
    CACHE_TTL = _int_env("CACHE_TTL", 600)

    # Limites de segurança para não sobrecarregar o archive.org.
    MAX_ROWS = 50
    ROWS_PER_PAGE = _int_env("ROWS_PER_PAGE", 30)
    REQUEST_TIMEOUT = _int_env("REQUEST_TIMEOUT", 15)
    QBT_TIMEOUT = _int_env("QBT_TIMEOUT", 10)
    HEALTH_TTL = _int_env("HEALTH_TTL", 30)

    USER_AGENT = (
        "JellyArchiveDownloader/1.0 "
        "(self-hosted; +https://github.com/Eliedson-luna/jelly-archive-downloader)"
    )

    # Endpoint JSON que o próprio site do archive.org usa para pesquisar.
    # title:(...) mantém a busca focada no título do filme (resultados muito
    # melhores que a busca full-text pura); {query} recebe o termo sanitizado.
    DEFAULT_SEARCH_URL = (
        "https://archive.org/advancedsearch.php"
        "?q=title%3A%28{query}%29+AND+mediatype%3A%22movies%22"
        "&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=year"
        "&fl%5B%5D=description&fl%5B%5D=downloads"
        "&sort%5B%5D=downloads+desc&rows={rows}&page=1&output=json"
    )

    # chave em settings -> variável de ambiente que a controla
    ENV_MANAGED = {
        "download_dir": "DOWNLOAD_DIR",
        "search_url": "SEARCH_URL",
        "qbittorrent_url": "QBT_URL",
        "qbittorrent_user": "QBT_USER",
        "qbittorrent_password": "QBT_PASS",
        "category": "QBT_CATEGORY",
    }
