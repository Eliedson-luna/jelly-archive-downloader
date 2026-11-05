# Imagem pensada para linux/arm/v7 (Armbian 32-bit).
# Construa na própria máquina de destino: docker compose build
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8088

# ca-certificates atualizado (o armbian costuma estar defasado) + curl para o healthcheck.
# Nenhuma dependência Python exige compilador (tudo pure-python), o que evita
# builds longos/instáveis em arm32.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh && mkdir -p /data

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
