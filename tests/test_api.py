"""API and ingestion behaviour: upload safety, idempotent re-index, scanned PDFs, concurrency, metrics.

Uses a deterministic hashing embedder so tests run in seconds without downloading a model.
"""
import hashlib
import io
import os
import sys
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ingest  # noqa: E402
import pipeline  # noqa: E402
from app import create_app  # noqa: E402
from store import Index  # noqa: E402
from vectorlitedb import VectorLiteDB  # noqa: E402

DIM = pipeline.EMBED_DIM


def fake_embed(texts):
    """Bag-of-words hashed into DIM buckets: same words -> same vector, overlapping words -> similar."""
    out = []
    for t in texts:
        v = np.zeros(DIM, dtype=np.float32)
        for w in t.lower().split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
        v[0] += 1e-3  # never all-zero
        out.append(v.tolist())
    return out


@pytest.fixture
def env(tmp_path):
    docs = tmp_path / "docs"
    db = tmp_path / "data" / "kb.db"
    app = create_app(embedder=fake_embed, db_path=str(db), docs_dir=str(docs))
    with TestClient(app) as client:
        yield client, tmp_path, docs, db


def upload(client, name, content: bytes):
    return client.post("/upload", files={"file": (name, io.BytesIO(content), "application/octet-stream")})


def blank_pdf(pages=2) -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


# --- upload safety ---

def test_path_traversal_is_contained(env):
    client, root, docs, _ = env
    r = upload(client, "../../escape.txt", b"graduate student researcher stipend")
    assert r.status_code == 200, r.text
    assert (docs / "escape.txt").exists()
    assert not (root / "escape.txt").exists()
    assert not (root.parent / "escape.txt").exists()


@pytest.mark.parametrize("name", ["notes.exe", "....", "../", ".pdf"])
def test_rejects_bad_names(env, name):
    client, _, docs, _ = env
    assert upload(client, name, b"text").status_code == 400
    assert list(docs.iterdir()) == []


def test_rejects_oversized_upload(env, monkeypatch):
    client, *_ = env
    monkeypatch.setattr(pipeline, "MAX_UPLOAD_BYTES", 10)
    assert upload(client, "big.txt", b"x" * 11).status_code == 413


# --- re-upload behaviour ---

def test_reupload_identical_is_noop(env):
    client, *_ = env
    body = b"fee remission " * 200  # several chunks
    first = upload(client, "policy.txt", body).json()
    second = upload(client, "policy.txt", body).json()
    assert second["unchanged"] is True
    assert second["chunks"] == first["chunks"]
    assert client.get("/health").json()["vectors"] == first["chunks"]


def test_reupload_changed_replaces_old_chunks(env):
    client, *_ = env
    long = upload(client, "policy.txt", b"tuition " * 500).json()
    short = upload(client, "policy.txt", b"nonresident supplemental tuition waived").json()
    assert long["chunks"] > 1 and short["chunks"] == 1
    assert client.get("/health").json()["vectors"] == 1
    files = {f["filename"]: f for f in client.get("/files").json()}
    assert files["policy.txt"]["count"] == 1


# --- extraction ---

def test_scanned_pdf_reports_reason(env):
    client, _, docs, _ = env
    r = upload(client, "scan.pdf", blank_pdf(3))
    assert r.status_code == 422
    assert "3 of 3 pages have no text layer" in r.json()["error"]
    assert not (docs / "scan.pdf").exists()


def test_corrupt_pdf_is_client_error(env):
    client, *_ = env
    assert upload(client, "broken.pdf", b"%PDF-not really").status_code == 422


def test_docx_tables_are_extracted():
    from docx import Document
    d = Document()
    d.add_paragraph("Stipend schedule")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "GSR Step 6", "$4,000"
    buf = io.BytesIO()
    d.save(buf)
    text = pipeline.extract_text(buf.getvalue(), "s.docx").text
    assert "GSR Step 6 | $4,000" in text


def test_sidecar_txt_is_not_indexed_twice(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "a.pdf.txt").write_text("copy")
    (tmp_path / "notes.txt").write_text("real")
    names = [os.path.basename(p) for p in pipeline.list_source_files(str(tmp_path))]
    assert names == ["a.pdf", "notes.txt"]


# --- search, metrics, files ---

def test_search_metrics_split_stages(env):
    client, *_ = env
    upload(client, "a.txt", b"nonresident supplemental tuition")
    upload(client, "b.txt", b"teaching assistant appointment hours")
    hits = client.get("/search", params={"q": "nonresident tuition", "k": 1}).json()
    assert hits[0]["metadata"]["file"] == "a.txt"
    filtered = client.get("/search", params={"q": "nonresident tuition", "k": 5, "file": "b.txt"}).json()
    assert {h["metadata"]["file"] for h in filtered} == {"b.txt"}
    m = client.get("/metrics").json()
    assert m["count"] == 2
    for key in ("p50_ms", "embed_p50_ms", "search_p50_ms"):
        assert m[key] is not None
    assert m["last_query"]["latency_ms"] == pytest.approx(
        m["last_query"]["embed_ms"] + m["last_query"]["search_ms"], abs=0.01)


def test_bench_and_parity(env):
    client, *_ = env
    b = client.get("/bench", params={"N": 300, "k": 5}).json()
    assert b["N"] == 300 and b["file_MB"] > 0
    assert client.get("/parity", params={"K": 5}).json()["ok"] is True


# --- index durability and concurrency ---

def test_index_survives_reload_and_writes_through_symlink(tmp_path):
    real = tmp_path / "outside" / "kb.db"
    real.parent.mkdir()
    link = tmp_path / "kb.db"
    idx = Index(str(real), dimension=DIM)
    os.symlink(real, link)
    idx = Index(str(link), dimension=DIM)
    idx.replace_file("x.txt", ["a", "b"], fake_embed(["a", "b"]), {"sha256": "h"})
    assert link.is_symlink(), "atomic save must not replace the symlink"
    assert len(VectorLiteDB(str(real))) == 2


def test_failed_save_leaves_index_unchanged(tmp_path, monkeypatch):
    idx = Index(str(tmp_path / "kb.db"), dimension=DIM)
    idx.replace_file("x.txt", ["a"], fake_embed(["a"]))
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        idx.replace_file("x.txt", ["b", "c"], fake_embed(["b", "c"]))
    assert len(idx) == 1
    assert len(VectorLiteDB(str(tmp_path / "kb.db"))) == 1


def test_concurrent_search_and_write(tmp_path):
    WRITERS = 8
    idx = Index(str(tmp_path / "kb.db"), dimension=DIM)
    idx.replace_file("seed.txt", ["seed"] * 50, fake_embed(["seed"] * 50))
    errors = []
    # Slow the save down so writers genuinely overlap. Race tests are probabilistic: without the
    # writer lock this fails most runs (writers clobber each other's temp file); with it, never.
    real_save = idx._db._save
    idx._db._save = lambda: (time.sleep(0.003), real_save())[1]

    def writer(i):
        try:
            for j in range(10):
                chunks = [f"doc {i} rev {j} part {p}" for p in range(20)]
                idx.replace_file(f"w{i}.txt", chunks, fake_embed(chunks))
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    def reader():
        try:
            for _ in range(50):
                idx.search(fake_embed(["seed"])[0], 5)
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(WRITERS)] + \
              [threading.Thread(target=reader) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(idx) == 50 + WRITERS * 20
    assert len(VectorLiteDB(str(tmp_path / "kb.db"))) == 50 + WRITERS * 20, "file on disk must match memory"


# --- incremental ingestion ---

def test_ingest_is_incremental_and_prunes(tmp_path, capsys):
    docs, db = tmp_path / "docs", tmp_path / "kb.db"
    docs.mkdir()
    (docs / "a.txt").write_text("graduate funding " * 100)
    (docs / "b.txt").write_text("fellowship rules")
    args = ["--docs", str(docs), "--db", str(db)]

    ingest.main(args, embedder=fake_embed)
    assert "2 indexed" in capsys.readouterr().out

    calls = []
    ingest.main(args, embedder=lambda t: calls.append(t) or fake_embed(t))
    assert calls == [] and "2 unchanged" in capsys.readouterr().out

    (docs / "b.txt").unlink()
    (docs / "a.txt").write_text("updated policy")
    ingest.main(args, embedder=fake_embed)
    out = capsys.readouterr().out
    assert "1 indexed" in out and "1 removed" in out
    assert set(Index(str(db), dimension=DIM).file_stats()) == {"a.txt"}
