"""Integração com o archive.org.

A página ``/details/movies?query=...`` é uma SPA (o HTML servido não contém os
resultados), por isso a busca usa o mesmo endpoint JSON que o site consome:
``/advancedsearch.php``. Os detalhes e o arquivo .torrent vêm de
``/metadata/<identifier>`` e ``/download/<identifier>/...``.
"""

import html
import re
from urllib.parse import quote, quote_plus

import requests

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
# Evita injeção de sintaxe na query do advancedsearch.php.
UNSAFE_QUERY_RE = re.compile(r"""[()\[\]{}"'\\/|!^~*?+=&<>:;]""")

DETAILS_URL = "https://archive.org/details/{identifier}"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{name}"
DOWNLOAD_LISTING_URL = "https://archive.org/download/{identifier}/"
TORRENT_LINK_RE = re.compile(r'href="([^"]+\.torrent)"', re.IGNORECASE)


class ArchiveError(Exception):
    """Falha ao falar com o archive.org ou interpretar a resposta."""


def sanitize_query(raw: str, limit: int = 200) -> str:
    """Remove caracteres que quebrariam a sintaxe de busca do archive.org."""
    text = WS_RE.sub(" ", str(raw or "")).strip()
    text = UNSAFE_QUERY_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text[:limit]


def build_search_url(template: str, query: str, rows: int) -> str:
    if "{query}" not in template:
        raise ArchiveError("A URL de busca precisa conter o marcador {query}.")
    url = template.replace("{query}", quote_plus(query))
    url = url.replace("{rows}", str(rows))
    return url


def _headers() -> dict:
    from flask import current_app

    return {"User-Agent": current_app.config["USER_AGENT"]}


def _timeout() -> int:
    from flask import current_app

    return int(current_app.config["REQUEST_TIMEOUT"])


def _extract_docs(payload) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    candidates = (
        ("response", "docs"),
        ("items",),
        ("docs",),
    )
    for path in candidates:
        current = payload
        for part in path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                current = None
                break
        if isinstance(current, list):
            return current
    return []


def clean_text(value, limit: int = 280) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    text = html.unescape(TAG_RE.sub(" ", str(value)))
    text = WS_RE.sub(" ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def normalize_doc(doc: dict) -> dict:
    downloads = doc.get("downloads")
    try:
        downloads = int(downloads)
    except (TypeError, ValueError):
        downloads = 0
    return {
        "identifier": str(doc.get("identifier") or "").strip(),
        "title": clean_text(doc.get("title"), limit=160) or "(sem título)",
        "year": clean_text(doc.get("year"), limit=12),
        "description": clean_text(doc.get("description")),
        "downloads": downloads,
        "details_url": DETAILS_URL.format(
            identifier=quote(str(doc.get("identifier") or ""), safe="")
        ),
    }


def search(template: str, query: str, rows: int) -> list:
    query = sanitize_query(query)
    if not query:
        raise ArchiveError("O termo de busca não contém caracteres válidos.")

    url = build_search_url(template, query, rows)
    try:
        response = requests.get(url, headers=_headers(), timeout=_timeout())
    except requests.RequestException as exc:
        raise ArchiveError(f"Falha ao consultar o archive.org: {exc}") from exc

    if response.status_code != 200:
        raise ArchiveError(f"O archive.org respondeu com HTTP {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ArchiveError(
            "A URL de busca não devolveu JSON. Verifique o modo configurado."
        ) from exc

    return [normalize_doc(doc) for doc in _extract_docs(payload) if doc.get("identifier")]


def _fetch_metadata_remote(identifier: str) -> dict:
    url = METADATA_URL.format(identifier=quote(identifier, safe=""))
    try:
        response = requests.get(url, headers=_headers(), timeout=_timeout())
    except requests.RequestException as exc:
        raise ArchiveError(f"Falha ao obter metadados: {exc}") from exc

    if response.status_code == 404:
        raise ArchiveError("Item não encontrado no archive.org.")
    if response.status_code != 200:
        raise ArchiveError(f"Metadados indisponíveis (HTTP {response.status_code}).")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ArchiveError("Metadados em formato inesperado.") from exc

    if not isinstance(payload, dict):
        raise ArchiveError("Metadados em formato inesperado.")
    return payload


def get_metadata(identifier: str) -> dict:
    """Metadados do item, com cache local para não repetir requisições."""
    from flask import current_app

    from app import db

    cached = db.cache_get(identifier, int(current_app.config["CACHE_TTL"]))
    if cached is not None:
        return cached

    payload = _fetch_metadata_remote(identifier)
    if payload.get("is_dark"):
        # itens escuros não são servidos; evita cachear por muito tempo
        payload["_dark"] = True
    else:
        db.cache_put(identifier, payload)
    return payload


def _fallback_torrent_url(identifier: str) -> tuple[str, str] | None:
    """Se o metadata não listar o .torrent, procura na listagem /download/."""
    url = DOWNLOAD_LISTING_URL.format(identifier=quote(identifier, safe=""))
    try:
        response = requests.get(url, headers=_headers(), timeout=_timeout())
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None

    match = TORRENT_LINK_RE.search(response.text)
    if not match:
        return None

    href = html.unescape(match.group(1))
    if href.startswith("http"):
        absolute = href
    elif href.startswith("/"):
        absolute = "https://archive.org" + href
    else:
        absolute = url + href.lstrip("./")
    name = absolute.rsplit("/", 1)[-1]
    return name, absolute


def resolve(identifier: str) -> dict:
    """Resolve um item para algo que o qBittorrent consiga baixar."""
    meta = get_metadata(identifier)
    meta_md = meta.get("metadata") or {}
    files = meta.get("files") or []

    title = clean_text(meta_md.get("title"), limit=200) or identifier
    result = {
        "identifier": identifier,
        "title": title,
        "description": clean_text(meta_md.get("description"), limit=1200),
        "year": clean_text(meta_md.get("year") or meta_md.get("date"), limit=12),
        "creator": clean_text(meta_md.get("creator"), limit=160),
        "mediatype": clean_text(meta_md.get("mediatype"), limit=40),
        "details_url": DETAILS_URL.format(identifier=quote(identifier, safe="")),
        "available": False,
        "reason": "",
        "torrent_name": "",
        "torrent_url": "",
        "torrent_size": 0,
        "total_size": 0,
        "files": [],
        "tracker": clean_text(meta.get("d1"), limit=120),
    }

    if meta.get("is_dark") or meta.get("_dark"):
        result["reason"] = "Este item está indisponível (marcado como escuro no archive.org)."
        return result

    try:
        result["total_size"] = int(meta.get("item_size") or 0)
    except (TypeError, ValueError):
        result["total_size"] = 0

    for entry in files:
        name = str(entry.get("name") or "")
        if not name:
            continue
        try:
            size = int(entry.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        fmt = str(entry.get("format") or "")
        result["files"].append(
            {"name": name, "format": fmt, "size": size, "is_torrent": name.endswith(".torrent")}
        )
        if not result["torrent_url"] and (
            name.endswith(".torrent") or "bittorrent" in fmt.lower()
        ):
            result["torrent_name"] = name
            result["torrent_url"] = DOWNLOAD_URL.format(
                identifier=quote(identifier, safe=""), name=quote(name, safe="/")
            )
            result["torrent_size"] = size

    if not result["torrent_url"]:
        fallback = _fallback_torrent_url(identifier)
        if fallback:
            result["torrent_name"], result["torrent_url"] = fallback

    if result["torrent_url"]:
        result["available"] = True
    else:
        result["reason"] = "Não há arquivo .torrent disponível para este item."

    result["files"] = result["files"][:300]
    return result


def fetch_torrent(url: str) -> bytes:
    try:
        response = requests.get(url, headers=_headers(), timeout=_timeout())
    except requests.RequestException as exc:
        raise ArchiveError(f"Falha ao baixar o .torrent: {exc}") from exc

    if response.status_code != 200:
        raise ArchiveError(f"O .torrent não pôde ser baixado (HTTP {response.status_code}).")

    content = response.content
    if not content or content[:1] != b"d":
        raise ArchiveError("O arquivo recebido não parece ser um torrent válido.")
    if len(content) > 5 * 1024 * 1024:
        raise ArchiveError("Arquivo .torrent grande demais.")
    return content
