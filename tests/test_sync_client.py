"""sync_client.py against a real app instance (both backends) and a mocked document server."""
import httpx
import pytest
from fastapi.testclient import TestClient

import sync_client
from app import create_app
from conftest import fake_embed


@pytest.fixture
def api(make_store, tmp_path):
    app = create_app(embedder=fake_embed, docs_dir=str(tmp_path / "served"), store=make_store())
    with TestClient(app) as client:
        yield client


def test_dir_sync_is_idempotent(api, tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("fee remission policy")
    (src / "b.md").write_text("teaching assistant hours")
    assert sync_client.main(["--dir", str(src)], api=api) == 0
    assert "2 indexed, 0 unchanged, 0 failed" in capsys.readouterr().out
    assert sync_client.main(["--dir", str(src)], api=api) == 0
    assert "0 indexed, 2 unchanged, 0 failed" in capsys.readouterr().out


def test_url_sync_reports_failures(api, tmp_path, capsys):
    pages = {"/policies/gsr%20rules.txt": b"graduate student researcher rules",
             "/policies/scan.pdf": b"%PDF-broken"}

    def handler(request: httpx.Request) -> httpx.Response:
        body = pages.get(request.url.raw_path.decode())
        return httpx.Response(200, content=body) if body is not None else httpx.Response(404)

    urls = tmp_path / "urls.txt"
    urls.write_text("# policy documents\n"
                    "https://example.edu/policies/gsr%20rules.txt\n\n"
                    "https://example.edu/policies/scan.pdf\n"
                    "https://example.edu/policies/missing.txt\n")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    code = sync_client.main(["--urls", str(urls)], api=api, http=http)
    out = capsys.readouterr().out
    assert code == 1, "a failed document must fail the Job"
    assert "indexed  gsr rules.txt" in out
    assert "1 indexed, 0 unchanged, 2 failed" in out
    hits = api.get("/search", params={"q": "graduate student researcher", "k": 1}).json()
    assert hits[0]["metadata"]["file"] == "gsr rules.txt"
