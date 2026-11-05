<div align="center">

# 🎬 Jelly Archive Downloader

**Busque, escolha e baixe filmes do Internet Archive via torrent — usando o qBittorrent que já roda no seu host.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-linux%2Farm%2Fv7-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![qBittorrent](https://img.shields.io/badge/qBittorrent-Web%20API-2F67B2?style=flat-square&logo=qbittorrent&logoColor=white)](https://www.qbittorrent.org/)
[![Fonte](https://img.shields.io/badge/fonte-somente%20archive.org-1B1B1B?style=flat-square&logo=internetarchive&logoColor=white)](https://archive.org/)
[![Testes](https://img.shields.io/badge/testes-41%20passando-2ea043?style=flat-square)](#-desenvolvimento)
[![Pegada](https://img.shields.io/badge/pegada-leve%20~100%20MB-4f8cff?style=flat-square)](#-hardware-alvo)

</div>

> [!IMPORTANT]
> **Este projeto baixa somente do [Internet Archive](https://archive.org).**
> A busca e a resolução do `.torrent` são específicas do archive.org — não é um
> buscador genérico de torrents. Veja o [guia completo](#-guia-baixar-do-internet-archive).

---

## 📚 Sumário

- [O que ele faz](#-o-que-ele-faz)
- [Escopo: somente Internet Archive](#-escopo-somente-internet-archive)
- [Como funciona](#-como-funciona)
- [Instalação rápida](#-instalação-rápida)
- [Configuração](#️-configuração)
- [Guia: baixar do Internet Archive](#-guia-baixar-do-internet-archive)
- [Onde ficam os dados](#-onde-ficam-os-dados)
- [Desenvolvimento](#-desenvolvimento)
- [Solução de problemas](#-solução-de-problemas)
- [Limitações](#-limitações)

## ✨ O que ele faz

- 🔎 **Busca** filmes no acervo público do archive.org e mostra o que tem torrent.
- 🧲 **Envia o `.torrent`** direto para o qBittorrent do host (Web API), já com
  categoria, `savepath` e tag.
- 📊 **Acompanha o progresso** em um histórico que se atualiza sozinho.
- ⚙️ **Configura tudo pela interface**: credenciais do qBittorrent, diretório de
  downloads e URL de busca.
- 🚨 **Avisa se o qBittorrent não estiver acessível** — banner em todas as páginas
  e download bloqueado.

## 🔒 Escopo: somente Internet Archive

| Dentro do escopo | Fora do escopo |
|---|---|
| Pesquisar no acervo público do archive.org | Índices genéricos (RARBG, 1337x, etc.) |
| Baixar itens que publicam `*_archive.torrent` | Magnet links arbitrários |
| Enviar o torrent ao qBittorrent do host | Baixar/gerenciar mídia dentro do container |
| Histórico dos envios | Player, transcodificação ou metadados para Jellyfin |

O que garante esse escopo é o **resolvedor de torrent**: ele consulta
`https://archive.org/metadata/<identifier>` e só aceita arquivos com formato
`Archive BitTorrent` (ou a listagem de `/download/<identifier>/`). Nenhuma outra
fonte é consultada.

## 🧭 Como funciona

```
navegador ──> Flask (container) ──HTTP──> qBittorrent do host (Web API)
                   │
                   ├── SQLite (/data/app.db): configurações + histórico + cache
                   └── HTTPS ──> archive.org (busca, metadados, .torrent)
```

1. **Busca** — a página `/details/movies?query=...` do archive.org é uma SPA
   (`<app-root>`), então o HTML servido não contém resultados. A aplicação usa o
   mesmo endpoint JSON do site: `advancedsearch.php`. A URL é configurável e
   precisa conter `{query}` (e opcionalmente `{rows}`).
2. **Disponibilidade** — cada card consulta `/metadata/<identifier>` (cache de
   10 min) e mostra se existe `.torrent` e o tamanho do conteúdo.
3. **Download** — o `.torrent` é baixado **em memória**, tem o **infohash**
   calculado localmente (SHA-1 do dicionário `info`) e é enviado ao qBittorrent
   com `savepath`, categoria e tag.
4. **Histórico** — status e progresso são reconciliados com
   `torrents/info?hashes=...` a cada 5 segundos.

## 🚀 Instalação rápida

```bash
git clone https://github.com/Eliedson-luna/jelly-archive-downloader.git
cd jelly-archive-downloader
cp .env.example .env      # ajuste QBT_PASS, DOWNLOAD_DIR, DATA_DIR_HOST
docker compose build
docker compose up -d
```

Acesse **http://IP-DO-SERVIDOR:8088**.

> A porta padrão é **8088** porque o qBittorrent já usa `8080`.

### Hardware alvo

| Item | Detalhe |
|---|---|
| Host | Armbian trixie, kernel 6.18 (Rockchip) |
| Arquitetura | **arm32 (armv7)** |
| RAM | 1 GB (container limitado a 256 MB; uso real ~100 MB) |
| Docker | 20+ com Compose |
| qBittorrent | no **host**, com **Web UI habilitada** |

### Antes de subir: qBittorrent no host

1. **Ferramentas → Preferências → Web UI** → marque *Web User Interface (Remote control)*.
2. Anote a porta (padrão `8080`) e defina usuário/senha.
3. Se o container não autenticar, marque temporariamente
   *"Bypass authentication for clients on localhost"* para testar.

## ⚙️ Configuração

Tudo em **Configurações** na interface:

| Campo | O que informar |
|---|---|
| URL do Web UI | `http://127.0.0.1:8080` |
| Usuário / Senha | credenciais da Web UI do qBittorrent |
| Categoria | categoria aplicada aos torrents (padrão `jelly`) |
| Diretório de downloads | **caminho do HOST**, ex.: `/home/eliedson/Downloads` |
| URL de busca | endpoint JSON do archive.org (já vem preenchido) |
| Resultados por página | 1–50 (padrão 30) |

Clique em **Testar conexão** para validar. Se o qBittorrent estiver fora do ar,
um alerta vermelho aparece em todas as páginas e o download fica bloqueado.

> **Diretório de downloads:** como o qBittorrent roda fora do container, o valor
> enviado em `savepath` precisa ser o caminho real da máquina. O container **não**
> monta essa pasta.
>
> **Credenciais:** usuário e senha podem ser alterados na interface. Se definir
> `QBT_USER`/`QBT_PASS` no `.env`, os campos ficam somente-leitura e o ambiente
> prevalece.

### Variáveis de ambiente

| Variável | Padrão | Função |
|---|---|---|
| `PORT` | `8088` | porta da interface |
| `TZ` | `America/Sao_Paulo` | fuso horário |
| `DATA_DIR_HOST` | `./data` | pasta do **host** montada em `/data` |
| `PUID` / `PGID` | `1000` | dono da pasta `DATA_DIR_HOST` |
| `QBT_URL` | — | Web UI do qBittorrent (vazio = usa a interface) |
| `QBT_USER` / `QBT_PASS` | — | credenciais (vazio = usa a interface) |
| `DOWNLOAD_DIR` | — | caminho do host para os downloads |
| `SEARCH_URL` | endpoint do archive.org | URL de busca com `{query}` |
| `DATA_DIR` | `/data` | caminho interno do SQLite |
| `CACHE_TTL` | `600` | cache de metadados (s) |
| `HEALTH_TTL` | `30` | cache da checagem do qBittorrent (s) |

Variáveis **vazias** são ignoradas (a interface manda). Variáveis preenchidas
sobrescrevem o banco a cada boot e travam o campo correspondente na tela.

## 📥 Guia: baixar do Internet Archive

### 1. O que é o Internet Archive

Biblioteca digital sem fins lucrativos que hospeda filmes de domínio público,
produções independentes, trailers, material histórico e muito mais. Cada item tem
um **identifier** (ex.: `night_of_the_living_dead_dvd`), que é a chave usada por
todas as URLs.

### 2. Como a busca funciona aqui

A URL padrão consulta o endpoint JSON usado pelo próprio site:

```
https://archive.org/advancedsearch.php?q=title:({query})+AND+mediatype:"movies"
  &fl[]=identifier&fl[]=title&fl[]=year&fl[]=description&fl[]=downloads
  &sort[]=downloads+desc&rows={rows}&page=1&output=json
```

- `{query}` é substituído pelo termo digitado, sanitizado (sem `(`, `)`, `:` e
  aspas, que quebrariam a sintaxe do archive.org).
- `{rows}` vira o limite de resultados.
- `title:({query})` foca no título do filme — resultados bem melhores que a busca
  full-text pura.
- A URL é editável: qualquer endpoint JSON equivalente funciona, desde que
  devolva `response.docs`, `items` ou `docs`.

### 3. Nem todo item tem torrent

| Situação | O que você vê |
|---|---|
| Item publica `*_archive.torrent` | selo verde `torrent` e botão **Adicionar** |
| Item sem torrent | selo vermelho `sem torrent`; download bloqueado |
| Item `is_dark` (removido, restrito ou DMCA) | `indisponível`, com o motivo |
| Item da *lending library* (empréstimo) | normalmente sem torrent público |

Quem não tem torrent ainda pode ser baixado manualmente pelo site do archive.org.

### 4. Por que baixa mesmo "sem peers"

Os torrents do archive.org trazem **web seeds** (`url-list`) apontando para os
servidores `ia*.us.archive.org`. O qBittorrent baixa por HTTP direto da origem,
mesmo que ninguém esteja semeando. Por isso o status *Sem peers* costuma se
resolver sozinho assim que o web seed responde.

### 5. Boas práticas

- O app limita a **50 resultados por página** e cacheia metadados por **10 min**.
- Não aumente o timeout nem dispare buscas em loop: é um serviço público.
- Use para **uso pessoal**, respeitando direitos autorais e os
  [termos do archive.org](https://archive.org/about/terms.php).
- ⚠️ Este projeto não contorna restrições: itens indisponíveis continuam
  indisponíveis.

## 🗂️ Onde ficam os dados

| Dado | Onde fica | Persistente |
|---|---|---|
| Configurações, histórico e cache de metadados | `DATA_DIR_HOST/app.db` (SQLite), no host | sim |
| Arquivos `.torrent` | em memória, apenas durante o envio ao qBittorrent | não |
| Filmes baixados | diretório de downloads do **host**, escritos pelo qBittorrent | sim (fora do container) |
| Cópia do `.torrent` gerida pelo qBittorrent | perfil do qBittorrent no host (`BT_backup/`) | sim (do qBittorrent) |

A pasta do host vem de `DATA_DIR_HOST` (padrão `./data`) e é montada em `/data`
dentro do container. Esse mount é de **tempo de execução** — não existe
"diretório de dados no build": o que é copiado no build fica dentro da imagem e é
descartado quando ela é recriada.

```bash
# compose, com outro diretório no host
DATA_DIR_HOST=/srv/jelly docker compose up -d

# docker run puro
docker run -d --network host -v /srv/jelly:/data jelly-archive-downloader:latest
```

Apagar `DATA_DIR_HOST` zera configurações e histórico; os filmes já baixados
**não** são afetados. Para backup, pare o container e copie o banco:

```bash
docker compose stop
cp data/app.db data/app.db.bak
docker compose start
```

Alternativa sem parar o container (SQLite em modo WAL):

```bash
sqlite3 data/app.db ".backup 'data/app.db.bak'"
```

## 🧪 Desenvolvimento

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python wsgi.py           # http://127.0.0.1:8088
.venv/bin/python -m pytest         # 41 testes
```

Sem Docker, use `QBT_URL` apontando para o qBittorrent local e `DATA_DIR=./data`.

### Estrutura

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
logs/                    # registro de sessões (ver AGENTS.md)
```

### Endpoints

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

## 🩺 Solução de problemas

| Sintoma | Causa provável |
|---|---|
| Banner “qBittorrent não detectado” | Web UI desabilitada, porta errada ou credenciais inválidas |
| `HTTP 403` no login | IP banido no qBittorrent após tentativas erradas — reinicie o serviço |
| Download adicionado mas “sem peers” | normal em itens antigos; o web seed do archive.org resolve |
| Erro de permissão em `./data` | ajuste `PUID`/`PGID` para o dono da pasta no host |
| `savepath` inválido no qBittorrent | o diretório precisa existir **no host**, não no container |
| Busca sem resultados | a URL de busca precisa conter `{query}` e devolver JSON |
| Selo “sem torrent” em tudo | item/coleção sem `.torrent`; teste outro identifier |

## 📌 Limitações

- **Somente Internet Archive** — por design.
- Sem autenticação: use apenas em rede local/confiável.
- Sem legendas, transcodificação ou integração direta com Jellyfin.
- Um único usuário e uma única instância de qBittorrent.
- Sem fila própria: o qBittorrent é a fonte da verdade.

---

<div align="center">
<sub>Feito para rodar em arm32 com 1 GB de RAM · <a href="https://archive.org">archive.org</a> · uso pessoal</sub>
</div>
