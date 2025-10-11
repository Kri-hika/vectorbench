import os, tempfile
from vectorlitedb import VectorLiteDB

def make(dbpath, metric):
    D=3
    db=VectorLiteDB(dbpath, dimension=D, distance_metric=metric)
    db.insert('x', [1,0,0], {"lab":"x"})
    db.insert('y', [0,1,0], {"lab":"y"})
    return db

def test_cosine_vs_l2_rankings():
    with tempfile.TemporaryDirectory() as d:
        cos = make(os.path.join(d,'c.db'), 'cosine')
        l2  = make(os.path.join(d,'l.db'), 'l2')
        q = [0.99, 0.01, 0]
        rc = [r['id'] for r in cos.search(q, top_k=2)]
        rl = [r['id'] for r in l2.search(q, top_k=2)]
        assert rc[0] == 'x'
        assert rl[0] == 'x'
