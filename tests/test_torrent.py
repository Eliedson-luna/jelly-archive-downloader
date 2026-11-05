import hashlib

import pytest

from app.services import torrent


def make_torrent(name: bytes = b"movie.mkv", length: int = 1024) -> bytes:
    info = {
        b"name": name,
        b"piece length": 16384,
        b"pieces": b"x" * 20,
        b"length": length,
    }
    return torrent.bencode({b"announce": b"http://bt1.archive.org:6969/announce", b"info": info})


def test_bencode_roundtrip():
    data = {b"a": 1, b"b": [b"x", 2], b"c": {b"d": b"y"}}
    assert torrent.bdecode(torrent.bencode(data)) == data


def test_infohash_matches_sha1_of_info_dict():
    data = make_torrent()
    info = torrent.bdecode(data)[b"info"]
    expected = hashlib.sha1(torrent.bencode(info)).hexdigest()
    assert torrent.infohash(data) == expected
    assert len(torrent.infohash(data)) == 40


def test_infohash_ignores_announce_and_extra_keys():
    base = torrent.bdecode(make_torrent())
    other = dict(base)
    other[b"comment"] = b"diferente"
    assert torrent.infohash(torrent.bencode(base)) == torrent.infohash(torrent.bencode(other))


def test_infohash_keeps_raw_bytes_of_info():
    info = {b"name": b"a.mkv", b"piece length": 16384, b"pieces": b"y" * 20, b"length": 5}
    raw = torrent.bencode({b"announce": b"http://x", b"info": info})
    assert torrent.info_slice(raw) == torrent.bencode(info)


def test_bdecode_rejects_invalid_data():
    with pytest.raises(torrent.BencodeError):
        torrent.bdecode(b"x")
    with pytest.raises(torrent.BencodeError):
        torrent.bdecode(b"d4:info")
    with pytest.raises(torrent.BencodeError):
        torrent.infohash(b"i3e")
