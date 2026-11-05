"""Cliente mínimo do Web API do qBittorrent (v4.1+ / v5.x)."""

import requests

CATEGORY_PREFIX = "jelly"


class QbtError(Exception):
    """Erro de comunicação ou de credenciais com o qBittorrent."""


def _friendly(exc: Exception, base_url: str) -> str:
    return (
        f"Não foi possível conectar ao qBittorrent em {base_url}. "
        "Verifique se o serviço está rodando e se a Web UI está habilitada "
        f"({exc.__class__.__name__})."
    )


class QBittorrentClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 10):
        self.base_url = (base_url or "").rstrip("/")
        self.username = username or ""
        self.password = password or ""
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Referer": self.base_url,
                "Origin": self.base_url,
                "User-Agent": "JellyDownloader/1.0",
            }
        )
        self._logged_in = False
        self._version = None

    # -- infraestrutura ----------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v2/{path.lstrip('/')}"

    def login(self) -> None:
        if not self.base_url:
            raise QbtError("A URL do qBittorrent não está configurada.")
        try:
            response = self.session.post(
                self._url("auth/login"),
                data={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise QbtError(_friendly(exc, self.base_url)) from exc

        if response.status_code == 403:
            raise QbtError(
                "O qBittorrent recusou o login. Verifique usuário/senha e, "
                "no qBittorrent, se o IP local está banido por tentativas falhas."
            )
        body = (response.text or "").strip()
        if response.status_code != 200 or body.lower() != "ok.":
            raise QbtError(
                "Login no qBittorrent falhou. Confira as credenciais da Web UI."
            )
        self._logged_in = True

    def _request(self, method: str, path: str, **kwargs):
        if not self._logged_in:
            self.login()

        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, self._url(path), **kwargs)
        except requests.RequestException as exc:
            raise QbtError(_friendly(exc, self.base_url)) from exc

        if response.status_code == 403:
            # cookie expirou: reautentica uma vez
            self._logged_in = False
            self.login()
            try:
                response = self.session.request(method, self._url(path), **kwargs)
            except requests.RequestException as exc:
                raise QbtError(_friendly(exc, self.base_url)) from exc

        if response.status_code >= 400:
            raise QbtError(
                f"qBittorrent respondeu HTTP {response.status_code} em {path}."
            )
        return response

    # -- operações ---------------------------------------------------------
    def version(self) -> str:
        if self._version:
            return self._version
        response = self._request("GET", "app/version")
        self._version = (response.text or "").strip()
        return self._version

    def _major_version(self) -> int:
        try:
            return int(self.version().lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            return 0

    def add_torrent(
        self,
        torrent_bytes: bytes,
        filename: str,
        savepath: str,
        category: str = "",
        paused: bool = False,
        tags: str = "",
    ) -> None:
        data = {
            "savepath": savepath,
            "category": category,
            "tags": tags,
            "autoTMM": "false",
        }
        # qBittorrent 5 renomeou "paused" para "stopped".
        key = "stopped" if self._major_version() >= 5 else "paused"
        data[key] = "true" if paused else "false"

        response = self._request(
            "POST",
            "torrents/add",
            files={
                "torrents": (
                    filename or "archive.torrent",
                    torrent_bytes,
                    "application/x-bittorrent",
                )
            },
            data=data,
        )
        body = (response.text or "").strip().lower()
        if body.startswith("fail"):
            raise QbtError(
                "O qBittorrent recusou o torrent (arquivo inválido ou já existente)."
            )

    def torrents_info(self, hashes: list[str] | None = None) -> list:
        params = {}
        if hashes:
            params["hashes"] = "|".join(hashes)
        response = self._request("GET", "torrents/info", params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise QbtError("Resposta inesperada do qBittorrent.") from exc
        return payload if isinstance(payload, list) else []

    def info_by_hash(self) -> dict:
        return {item.get("hash", "").lower(): item for item in self.torrents_info()}

    def delete(self, hashes: list[str], delete_files: bool = False) -> None:
        if not hashes:
            return
        self._request(
            "POST",
            "torrents/delete",
            data={
                "hashes": "|".join(hashes),
                "deleteFiles": "true" if delete_files else "false",
            },
        )

    def create_category(self, name: str, savepath: str = "") -> None:
        if not name:
            return
        self._request(
            "POST",
            "torrents/createCategory",
            data={"category": name, "savePath": savepath},
        )


def client_from_settings(settings: dict) -> QBittorrentClient:
    from flask import current_app

    return QBittorrentClient(
        base_url=settings.get("qbittorrent_url", ""),
        username=settings.get("qbittorrent_user", ""),
        password=settings.get("qbittorrent_password", ""),
        timeout=int(current_app.config["QBT_TIMEOUT"]),
    )


def map_status(torrent: dict) -> tuple[str, float]:
    """Traduz o estado do qBittorrent para o status exibido no histórico."""
    progress = float(torrent.get("progress") or 0)
    state = str(torrent.get("state") or "").lower()

    if state in {"error", "missingfiles"}:
        return "error", progress
    if progress >= 0.999:
        return "completed", progress
    if state.startswith("paused") or state.startswith("stopped"):
        return "paused", progress
    if state in {"queueddl", "queuedup", "metadl", "checkingdl", "checkingup", "checkingresume",
                 "allocating", "moving"}:
        return "queued", progress
    if state.startswith("stalled"):
        return "stalled", progress
    if state.startswith("forced"):
        return "downloading", progress
    return "downloading", progress
