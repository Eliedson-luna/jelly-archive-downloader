"""Proteção CSRF mínima baseada em sessão.

Não adiciona dependências: o token fica na sessão assinada do Flask e é exigido
em todo método que altera estado (POST/PUT/PATCH/DELETE). Formulários enviam o
token no campo ``_csrf_token``; chamadas ``fetch`` enviam no header
``X-CSRF-Token``.
"""

import hmac
import secrets

from flask import abort, current_app, request, session

SESSION_KEY = "_csrf_token"
FORM_FIELD = "_csrf_token"
HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def token() -> str:
    """Devolve o token da sessão, criando-o no primeiro uso."""
    value = session.get(SESSION_KEY)
    if not value:
        value = secrets.token_urlsafe(32)
        session[SESSION_KEY] = value
    return value


def protect() -> None:
    """Bloqueia requisições mutantes sem token válido."""
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method in SAFE_METHODS:
        return

    expected = session.get(SESSION_KEY)
    provided = request.form.get(FORM_FIELD) or request.headers.get(HEADER) or ""
    if not expected or not provided or not hmac.compare_digest(str(expected), str(provided)):
        abort(400, description="Token CSRF inválido ou ausente. Recarregue a página.")
