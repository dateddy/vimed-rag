"""Test cho src.data.chunker: size/overlap đúng, không mất token ở biên."""

from src.config import ChunkingConfig
from src.data.chunker import chunk_documents, chunk_text


def test_chunk_size_and_overlap():
    tokens = [str(i) for i in range(10)]
    text = " ".join(tokens)
    chunks = chunk_text(text, size=4, overlap=1)
    # step = 3 -> bắt đầu tại 0,3,6,9
    assert chunks[0].split() == ["0", "1", "2", "3"]
    assert chunks[1].split() == ["3", "4", "5", "6"]
    # chunk kề nhau chồng lấn đúng 1 token
    assert chunks[0].split()[-1] == chunks[1].split()[0]


def test_no_token_lost_at_boundary():
    tokens = [str(i) for i in range(10)]
    text = " ".join(tokens)
    chunks = chunk_text(text, size=4, overlap=1)
    covered = set()
    for c in chunks:
        covered.update(c.split())
    assert covered == set(tokens)
    # token cuối cùng phải xuất hiện trong chunk cuối
    assert "9" in chunks[-1].split()


def test_short_text_single_chunk():
    chunks = chunk_text("a b", size=4, overlap=1)
    assert chunks == ["a b"]


def test_empty_text():
    assert chunk_text("", size=4, overlap=1) == []


def test_chunk_documents_uses_config():
    cfg = ChunkingConfig(size=2, overlap=0)
    out = chunk_documents(["a b c d"], cfg)
    assert out == ["a b", "c d"]
