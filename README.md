# Jelly Downloader

Interface web simples para pesquisar filmes no [archive.org](https://archive.org)
e enviá-los ao **qBittorrent que roda no host**, baixando via torrent quando o
item disponibiliza um arquivo `.torrent`.

> O container **não** contém o qBittorrent. Ele conversa com o qBittorrent do
> sistema pela Web API.

## Requisitos

| Item | Detalhe |
|---|---|
| Host | Armbian / Debian em **arm32 (armv7)** |
| Docker | 20+ com Docker Compose |
| qBittorrent | instalado no **host**, com a **Web UI habilitada** |
| Rede | `network_mode: host` (o container precisa alcançar `127.0.0.1:8080`) |

## 1. Preparar o qBittorrent (no host)

1. Abra o qBittorrent → **Ferramentas → Preferências → Web UI**.
2. Marque **Web User Interface (Remote control)**.
3. Anote a porta (padrão `8080`) e defina usuário/senha.
4. Se o container não conseguir autenticar, marque temporariamente
   **"Bypass authentication for clients on localhost"** para testar.

## 2. Subir o container

```bash
cp .env.example .env
# edite o .env (senha do qBittorrent, DOWNLOAD_DIR, DATA_DIR_HOST, etc.)
docker compose build      # construa na própria máquina arm32
docker compose up -d
```

Acesse **http://IP-DO-SERVIDOR:8088**.

Quer guardar configurações/histórico em outro lugar do host? Basta apontar
`DATA_DIR_HOST` (ver [Onde ficam os dados](#onde-ficam-os-dados)):

```bash
DATA_DIR_HOST=/srv/jelly docker compose up -d
```

> A porta padrão da interface é **8088** porque o qBittorrent já usa `8080`.
> Ela é definida por `PORT` no `.env` (ou `environment` do compose).

## 3. Configurar pela interface

Em **Configurações**:

| Campo | O que informar |
|---|---|
| URL do Web UI | `http://127.0.0.1:8080` |
| Usuário / Senha | credenciais da Web UI do qBittorrent |
| Categoria | categoria aplicada aos torrents (padrão `jelly`) |
| Diretório de downloads | **caminho do HOST**, ex.: `/home/eliedson/Downloads` |
| URL de busca | endpoint JSON do archive.org (já vem preenchido) |

Clique em **Testar conexão** para confirmar. Se o qBittorrent estiver fora do
ar, um alerta vermelho aparece em todas as páginas e o download fica bloqueado.

> **Credenciais:** usuário e senha são os mesmos da Web UI do qBittorrent e
> podem ser alterados aqui. Se você definir `QBT_USER`/`QBT_PASS` no `.env`,
> os campos ficam somente-leitura e o valor do ambiente prevalece.

> **Atenção ao diretório:** como o qBittorrent roda fora do container, o valor
> enviado em `savepath` precisa ser o caminho real da máquina. O container
> **não** monta a pasta de downloads.

## Como funciona

```
navegador ──> Flask (container) ──HTTP──> qBittorrent do host (Web API)
                   │
                   ├── SQLite (/data/app.db): configurações + histórico
                   └── HTTPS ──> archive.org
```

1. **Busca** — a página `/details/movies?query=...` do archive.org é uma SPA
   (`<app-root>`), então o HTML servido não contém resultados. A aplicação usa
   o mesmo endpoint JSON que o site consome: `advancedsearch.php`. A URL é
   configurável e precisa conter `{query}` (e opcionalmente `{rows}`).
2. **Disponibilidade** — cada card consulta `/metadata/<identifier>` (com cache
   de 10 min) e mostra se existe `.torrent` e o tamanho do conteúdo.
3. **Download** — o `.torrent` é baixado **em memória** (não é gravado em
   disco), tem o **infohash** calculado localmente (SHA-1 do dicionário `info`)
   e é enviado ao qBittorrent com `savepath`, categoria e tag
   `jelly-downloader`.
4. **Histórico** — status e progresso são reconciliados com
   `torrents/info?hashes=...` a cada 5 segundos.

Torrents do archive.org trazem *web seeds* (`url-list`), então o download
funciona mesmo quando não há peers.

## Onde ficam os dados

| Dado | Onde fica | Persistente |
|---|---|---|
| Configurações, histórico e cache de metadados | `DATA_DIR_HOST/app.db` (SQLite), no host | sim |
| Arquivos `.torrent` | em memória, apenas durante o envio ao qBittorrent | não |
| Filmes baixados | diretório de downloads do **host**, escritos pelo qBittorrent | sim (fora do container) |
| Cópia do `.torrent` gerida pelo qBittorrent | perfil do qBittorrent no host (`BT_backup/`) | sim (do qBittorrent) |

A pasta do host vem de `DATA_DIR_HOST` (padrão `./data`) e é montada em `/data`
dentro do container. Esse mount é de **tempo de execução** — não existe
"diretório de dados no build": o que é copiado no build fica dentro da imagem e
é descartado quando ela é recriada.

```bash
# compose
DATA_DIR_HOST=/srv/jelly docker compose up -d

# docker run puro
docker run -d --network host -v /srv/jelly:/data jelly-downloader:latest
```

Apagar `DATA_DIR_HOST` zera configurações e histórico; os filmes já baixados
**não** são afetados (eles pertencem ao qBittorrent). Para backup, pare o
container e copie o banco:

```bash
docker compose stop
cp data/app.db data/app.db.bak
docker compose start
```

Alternativa sem parar o container (SQLite em modo WAL):

```bash
sqlite3 data/app.db ".backup 'data/app.db.bak'"
```

## Estrutura do projeto

```
app/
├── __init__.py          # fábrica Flask, filtros, /health
├── config.py            # padrões + variáveis de ambiente
├── db.py                # SQLite (settings, downloads, cache)
├── routes/              # search, item, history, settings
├── services/
│   ├── archive.py       # busca JSON, metadados, resolução do .torrent
│   ├── qbittorrent.py   # cliente do Web API
│   ├── torrent.py       # bencode + infohash
│   └── health.py        # checagem de disponibilidade do qBittorrent
├── templates/           # Jinja2
└── static/              # CSS + JS (sem build step)
docker/entrypoint.sh     # PUID/PGID + waitress
tests/                   # pytest
```

## Variáveis de ambiente

| Variável | Padrão | Função |
|---|---|---|
| `PORT` | `8088` | porta da interface |
| `TZ` | `America/Sao_Paulo` | fuso horário |
| `DATA_DIR_HOST` | `./data` | pasta do **host** montada em `/data` |
| `PUID` / `PGID` | `1000` | dono da pasta `DATA_DIR_HOST` |
| `QBT_URL` | `http://127.0.0.1:8080` | Web UI do qBittorrent |
| `QBT_USER` / `QBT_PASS` | `admin` / — | credenciais |
| `DOWNLOAD_DIR` | — | caminho do host para os downloads |
| `SEARCH_URL` | endpoint do archive.org | URL de busca com `{query}` |
| `DATA_DIR` | `/data` | caminho interno do SQLite (ajuste o volume se mudar) |
| `CACHE_TTL` | `600` | cache de metadados (s) |
| `HEALTH_TTL` | `30` | cache da checagem do qBittorrent (s) |

Variáveis definidas sobrescrevem o banco a cada boot; nesse caso o campo
correspondente fica somente-leitura na interface. Variáveis **vazias** são
ignoradas (a interface manda).

## Desenvolvimento

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python wsgi.py           # http://127.0.0.1:8088
.venv/bin/python -m pytest
```

Sem Docker, use `QBT_URL` apontando para o qBittorrent local e `DATA_DIR=./data`.

## Endpoints

| Rota | Descrição |
|---|---|
| `/` | página de busca |
| `/search?q=` | resultados |
| `/item/<identifier>` | detalhe + botão de download |
| `/history` | histórico |
| `/api/history` | HTML parcial (poll de 5 s) |
| `/api/torrent-check/<identifier>` | JSON com disponibilidade |
| `/api/test-connection` | testa o qBittorrent (força) |
| `/settings` | configurações |
| `/health` | healthcheck do container |

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| Banner “qBittorrent não detectado” | Web UI desabilitada, porta errada ou credenciais inválidas |
| `HTTP 403` no login | IP banido no qBittorrent após tentativas erradas — reinicie o serviço ou ajuste as opções de banimento |
| Download adicionado mas “sem peers” | normal em itens antigos; o qBittorrent usa os *web seeds* do archive.org |
| Erro de permissão em `./data` | ajuste `PUID`/`PGID` para o dono da pasta no host |
| `savepath` inválido no qBittorrent | o diretório precisa existir **no host**, não dentro do container |
| Busca sem resultados | a URL de busca precisa conter `{query}` e devolver JSON |

## Limitações (v1)

- Sem autenticação — use apenas em rede local/confiável.
- Sem legendas, transcodificação ou integração com Jellyfin.
- Um único usuário e uma única instância de qBittorrent.
- Somente a fonte archive.org (a busca é configurável, mas o resolvedor de
  torrent é específico do archive.org).
