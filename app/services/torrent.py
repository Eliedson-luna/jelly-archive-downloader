"""Leitura mínima de torrents (bencode) e cálculo do infohash.

O Web API do qBittorrent não devolve o hash ao adicionar um torrent, então
calculamos localmente o SHA-1 do dicionário ``info`` — exatamente o mesmo
algoritmo usado pelos clientes BitTorrent.
"""

import hashlib


class BencodeError(ValueError):
    pass


def _decode(data: bytes, pos: int = 0):
    if pos >= len(data):
        raise BencodeError("fim inesperado dos dados")

    ch = data[pos : pos + 1]

    if ch == b"i":
        end = data.find(b"e", pos)
        if end < 0:
            raise BencodeError("inteiro sem terminador")
        return int(data[pos + 1 : end]), end + 1

    if ch == b"l":
        pos += 1
        out = []
        while data[pos : pos + 1] != b"e":
            value, pos = _decode(data, pos)
            out.append(value)
        return out, pos + 1

    if ch == b"d":
        pos += 1
        out = {}
        while data[pos : pos + 1] != b"e":
            key, pos = _decode(data, pos)
            if not isinstance(key, bytes):
                raise BencodeError("chave de dicionário inválida")
            value, pos = _decode(data, pos)
            out[key] = value
        return out, pos + 1

    if ch.isdigit():
        sep = data.find(b":", pos)
        if sep < 0:
            raise BencodeError("string sem separador de tamanho")
        length = int(data[pos:sep])
        start = sep + 1
        end = start + length
        if end > len(data):
            raise BencodeError("string truncada")
        return data[start:end], end

    raise BencodeError(f"token inválido na posição {pos}")


def bdecode(data: bytes):
    value, _ = _decode(data)
    return value


def bencode(value) -> bytes:
    if isinstance(value, str):
        value = value.encode()
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    if isinstance(value, bool):
        return b"i%de" % int(value)
    if isinstance(value, int):
        return b"i%de" % value
    if isinstance(value, list):
        return b"l" + b"".join(bencode(v) for v in value) + b"e"
    if isinstance(value, dict):
        items = []
        for key, val in value.items():
            if isinstance(key, str):
                key = key.encode()
            items.append((key, val))
        items.sort(key=lambda kv: kv[0])
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"
    raise BencodeError(f"tipo não suportado: {type(value)!r}")


def info_slice(data: bytes) -> bytes:
    """Extrai os bytes crus do valor ``info`` sem recodificar o dicionário."""
    if data[:1] != b"d":
        raise BencodeError("torrent inválido: esperado dicionário")

    pos = 1
    while pos < len(data) and data[pos : pos + 1] != b"e":
        key, pos = _decode(data, pos)
        start = pos
        _, pos = _decode(data, pos)
        if key == b"info":
            return data[start:pos]

    raise BencodeError("torrent sem chave 'info'")


def infohash(data: bytes) -> str:
    return hashlib.sha1(info_slice(data)).hexdigest()
