"""The VectorStore contract, run against both backends, plus each backend's own failure modes."""
import os
import threading
import time

import numpy as np
import pytest

from conftest import DIM, fake_embed
from store import VectorLiteStore
from vectorlitedb import VectorLiteDB


def vecs(texts):
    return fake_embed(texts)


# --- contract: both backends must behave identically ---

def test_replace_search_delete_roundtrip(make_store):
    s = make_store()
    s.replace_file("a.txt", ["tuition waiver", "fee remission"], vecs(["tuition waiver", "fee remission"]), sha256="ha")
    s.replace_file("b.txt", ["teaching hours"], vecs(["teaching hours"]), sha256="hb")
    assert len(s) == 3
    assert s.file_stats() == {"a.txt": {"chunks": 2, "sha256": "ha"}, "b.txt": {"chunks": 1, "sha256": "hb"}}
    assert s.file_sha256("a.txt") == "ha" and s.file_sha256("missing.txt") is None

    hit = s.search(vecs(["fee remission"])[0], 1)[0]
    assert hit["id"] == "a.txt::1"
    assert hit["similarity"] == pytest.approx(1.0, abs=1e-5)
    assert hit["metadata"] == {"file": "a.txt", "index": 1, "chunk": "fee remission",
                               "file_type": "txt", "sha256": "ha"}

    assert s.delete_file("a.txt") == 2
    assert len(s) == 1 and set(s.file_stats()) == {"b.txt"}
    assert s.delete_file("a.txt") == 0


def test_replace_swaps_all_chunks(make_store):
    s = make_store()
    s.replace_file("a.txt", [f"old {i}" for i in range(10)], vecs([f"old {i}" for i in range(10)]))
    s.replace_file("a.txt", ["new"], vecs(["new"]))
    assert len(s) == 1
    assert [h["metadata"]["chunk"] for h in s.search(vecs(["old 3"])[0], 10)] == ["new"]


def test_file_filter_returns_k_hits_from_that_file_only(make_store):
    """Contract: k hits, all from the requested file, even when every other chunk is closer.
    (pgvector filters after an HNSW scan, so store_pg ranks a filtered file's rows exactly; on small
    tables Postgres would use the primary key anyway, so this pins the contract, not the plan.)"""
    s = make_store()
    near = [f"stipend amount {i}" for i in range(200)]
    s.replace_file("near.txt", near, vecs(near))
    far = [f"parking permit rules {i}" for i in range(5)]
    s.replace_file("far.txt", far, vecs(far))
    hits = s.search(vecs(["stipend amount"])[0], 3, file="far.txt")
    assert len(hits) == 3 and {h["metadata"]["file"] for h in hits} == {"far.txt"}


def test_rejects_wrong_dimension_and_mismatched_lengths(make_store):
    s = make_store()
    with pytest.raises(ValueError):
        s.replace_file("a.txt", ["x"], [[0.0] * (DIM - 1)])
    with pytest.raises(ValueError):
        s.replace_file("a.txt", ["x", "y"], vecs(["x"]))
    assert len(s) == 0


def test_concurrent_writers_and_readers(make_store):
    s = make_store()
    s.replace_file("seed.txt", ["seed"] * 50, vecs(["seed"] * 50))
    errors, writers = [], 6

    def writer(i):
        try:
            for j in range(5):
                chunks = [f"doc {i} rev {j} part {p}" for p in range(20)]
                s.replace_file(f"w{i}.txt", chunks, vecs(chunks))
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    def reader():
        try:
            for _ in range(30):
                s.search(vecs(["seed"])[0], 5)
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(writers)] + \
              [threading.Thread(target=reader) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(s) == 50 + writers * 20


# --- embedded store: durability on a single file ---

def test_vectorlite_writes_through_symlink(tmp_path):
    real = tmp_path / "outside" / "kb.db"
    real.parent.mkdir()
    VectorLiteStore(str(real), dimension=DIM)
    link = tmp_path / "kb.db"
    os.symlink(real, link)
    VectorLiteStore(str(link), dimension=DIM).replace_file("x.txt", ["a", "b"], vecs(["a", "b"]))
    assert link.is_symlink(), "atomic save must not replace the symlink"
    assert len(VectorLiteDB(str(real))) == 2


def test_vectorlite_failed_save_leaves_index_unchanged(tmp_path, monkeypatch):
    s = VectorLiteStore(str(tmp_path / "kb.db"), dimension=DIM)
    s.replace_file("x.txt", ["a"], vecs(["a"]))
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        s.replace_file("x.txt", ["b", "c"], vecs(["b", "c"]))
    assert len(s) == 1
    assert len(VectorLiteDB(str(tmp_path / "kb.db"))) == 1


def test_vectorlite_writers_do_not_clobber_the_file(tmp_path):
    """Race tests are probabilistic: with the save slowed down, removing the writer lock makes this
    fail most runs (writers overwrite each other's temp file); with the lock it never fails."""
    s = VectorLiteStore(str(tmp_path / "kb.db"), dimension=DIM)
    s.replace_file("seed.txt", ["seed"] * 50, vecs(["seed"] * 50))
    real_save = s._db._save
    s._db._save = lambda: (time.sleep(0.003), real_save())[1]
    writers = 8

    def writer(i):
        for j in range(10):
            chunks = [f"doc {i} rev {j} part {p}" for p in range(20)]
            s.replace_file(f"w{i}.txt", chunks, vecs(chunks))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(VectorLiteDB(str(tmp_path / "kb.db"))) == 50 + writers * 20, "file on disk must match memory"


# --- pgvector: transactions, shared schema, approximate search ---

def test_pg_same_file_writers_serialize(pg_factory):
    """Two replicas re-indexing the same file at once: without the per-file advisory lock the second
    transaction's insert collides with the first's rows (primary-key violation)."""
    stores = [pg_factory(), pg_factory()]
    errors = []

    def writer(s, tag):
        try:
            for j in range(15):
                chunks = [f"{tag} rev {j} part {p}" for p in range(10)]
                s.replace_file("shared.txt", chunks, vecs(chunks), sha256=f"{tag}{j}")
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(s, t)) for s, t in zip(stores, "ab")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert stores[0].file_stats()["shared.txt"]["chunks"] == 10


def test_pg_replicas_create_schema_once(pg_factory):
    """Replicas starting together all run schema setup; the advisory lock makes that safe."""
    errors = []

    def start():
        try:
            pg_factory()
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    threads = [threading.Thread(target=start) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_pg_failed_write_rolls_back(pg_factory):
    s = pg_factory()
    s.replace_file("a.txt", ["kept"], vecs(["kept"]), sha256="v1", source=b"v1")
    bad = vecs(["x", "y"])
    bad[1] = [float("nan")] * DIM  # pgvector rejects NaN, mid-COPY
    with pytest.raises(Exception):
        s.replace_file("a.txt", ["x", "y"], bad, sha256="v2", source=b"v2")
    assert s.file_stats() == {"a.txt": {"chunks": 1, "sha256": "v1"}}
    assert s.source("a.txt") == b"v1"


def test_pg_exact_and_hnsw_agree_on_easy_queries(pg_factory):
    rng = np.random.default_rng(0)
    X = rng.standard_normal((500, DIM)).astype("float32")
    s = pg_factory()
    s.replace_file("r.txt", [str(i) for i in range(500)], X.tolist())
    exact = s.with_search("exact")
    try:
        for i in (3, 77, 401):  # a stored vector's nearest neighbour is itself
            assert s.search(X[i], 1)[0]["id"] == exact.search(X[i], 1)[0]["id"] == f"r.txt::{i}"
    finally:
        exact.close()


def test_pg_returns_k_results_when_k_exceeds_ef_search(pg_factory):
    s = pg_factory(ef_search=10)
    chunks = [f"chunk {i}" for i in range(100)]
    s.replace_file("a.txt", chunks, vecs(chunks))
    assert len(s.search(vecs(["chunk"])[0], 50)) == 50


def test_pg_rejects_unsafe_schema_name():
    pytest.importorskip("psycopg", reason="pgvector extras not installed")
    from store_pg import PgVectorStore
    with pytest.raises(ValueError):
        PgVectorStore("postgresql://unused", schema="x; DROP TABLE chunks")


def test_vectorlite_unreadable_index_names_the_file_and_fix(tmp_path, capsys):
    import ingest
    from store import CorruptIndexError
    db = tmp_path / "kb.db"
    VectorLiteStore(str(db), dimension=DIM).replace_file("a.txt", ["fee remission"], vecs(["fee remission"]))
    db.write_bytes(db.read_bytes()[: len(db.read_bytes()) // 2])  # truncated, as by an old non-atomic save

    with pytest.raises(CorruptIndexError, match="ingest.py --rebuild") as err:
        VectorLiteStore(str(db), dimension=DIM)
    assert str(db) in str(err.value)

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("fee remission")
    ingest.main(["--docs", str(docs), "--db", str(db), "--store", "vectorlite", "--rebuild"], embedder=fake_embed)
    assert "1 indexed" in capsys.readouterr().out
    assert set(VectorLiteStore(str(db), dimension=DIM).file_stats()) == {"a.txt"}
