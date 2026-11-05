#!/bin/sh
# Ajusta o dono do volume e roda a aplicação com o UID/GID do usuário do host,
# para que o banco SQLite em /data não fique pertencendo ao root.
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
PORT="${PORT:-8088}"
DATA_DIR="${DATA_DIR:-/data}"
THREADS="${THREADS:-4}"

mkdir -p "$DATA_DIR"
chown -R "$PUID:$PGID" "$DATA_DIR" 2>/dev/null || true

exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups \
    python -m waitress --listen="0.0.0.0:${PORT}" --threads="${THREADS}" wsgi:app
