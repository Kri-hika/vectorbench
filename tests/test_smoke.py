import os
import tempfile
import pytest
from vectorlitedb import VectorLiteDB

@pytest.fixture()
def tmpdb():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.db")
        yield path

def test_crud_and_search(tmpdb):
    D = 4
    db = VectorLiteDB(tmpdb, dimension=D, distance_metric="cosine")

    db.insert(id="a", vector=[1,0,0,0], metadata={"type":"doc"})
    db.insert(id="b", vector=[0.9,0.1,0,0], metadata={"type":"doc"})
    db.insert(id="c", vector=[0,1,0,0], metadata={"type":"note"})
    assert len(db) == 3

    v, m = db.get("a")
    assert isinstance(v, list) and m["type"] == "doc"

    res = db.search(query=[0.95,0.05,0,0], top_k=2)
    assert isinstance(res, list) and {r['id'] for r in res} <= {"a","b","c"}

    res_f = db.search(query=[0.95,0.05,0,0], top_k=5,
                      filter=lambda meta: meta.get("type") == "doc")
    assert all(r['metadata'].get('type') == 'doc' for r in res_f)

    db.delete("c")
    assert len(db) == 2

def test_dimension_guard(tmpdb):
    db = VectorLiteDB(tmpdb, dimension=3)
    import pytest
    with pytest.raises(Exception):
        db.insert(id="x", vector=[1,2,3,4], metadata={})
