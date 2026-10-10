"""Shared fixtures. Store-level and API tests run once per backend.

pgvector tests need a database: set VB_TEST_PG_DSN (e.g. postgresql://postgres:postgres@localhost:5432/postgres).
Each test gets its own Postgres schema, dropped afterwards. Without the variable those tests are skipped.
"""
import hashlib
import os
import sys
import uuid

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline  # noqa: E402
from store import VectorLiteStore  # noqa: E402

DIM = pipeline.EMBED_DIM
PG_DSN = os.getenv("VB_TEST_PG_DSN")
BACKENDS = ["vectorlite", "pgvector"]


def fake_embed(texts):
    """Bag-of-words hashed into DIM buckets: same words -> same vector, overlapping words -> similar.
    Deterministic and instant, so tests never download a model."""
    out = []
    for t in texts:
        v = np.zeros(DIM, dtype=np.float32)
        for w in t.lower().split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
        v[0] += 1e-3  # never all-zero
        out.append(v.tolist())
    return out


class StoreFactory:
    """Opens stores of one backend; pgvector stores opened here share one throwaway schema."""

    def __init__(self, kind, tmp_path):
        self.kind, self.tmp_path = kind, tmp_path
        self.schema = f"t_{uuid.uuid4().hex[:12]}"
        self.opened = []

    def __call__(self, **kw):
        if self.kind == "vectorlite":
            s = VectorLiteStore(str(self.tmp_path / "data" / "kb.db"), dimension=DIM)
        else:
            from store_pg import PgVectorStore
            s = PgVectorStore(PG_DSN, DIM, schema=self.schema, **kw)
        self.opened.append(s)
        return s

    def cleanup(self):
        for s in self.opened:
            s.close()
        if self.kind == "pgvector" and self.opened:
            import psycopg
            from psycopg import sql
            with psycopg.connect(PG_DSN, autocommit=True) as conn:
                conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(self.schema)))


@pytest.fixture(params=BACKENDS)
def backend(request):
    if request.param == "pgvector" and not PG_DSN:
        pytest.skip("set VB_TEST_PG_DSN to run pgvector tests")
    return request.param


@pytest.fixture
def make_store(backend, tmp_path):
    factory = StoreFactory(backend, tmp_path)
    yield factory
    factory.cleanup()


@pytest.fixture
def pg_factory(tmp_path):
    """For pgvector-only tests."""
    if not PG_DSN:
        pytest.skip("set VB_TEST_PG_DSN to run pgvector tests")
    factory = StoreFactory("pgvector", tmp_path)
    yield factory
    factory.cleanup()
