"""Push documents into a running VectorBench API through /upload.

Every write goes through the API, so the API stays the only writer to the store (required for the
embedded store, and the same code path as user uploads for pgvector). Uploads are idempotent: files
whose content has not changed come back as "unchanged" and cost no re-embedding, which makes this safe
to run on a schedule (see k8s/pgvector/sync-cronjob.yaml).

  python sync_client.py --api http://127.0.0.1:8000 --dir docs/
  python sync_client.py --api http://vectorbench-api:8000 --urls /config/urls.txt

A URL list has one URL per line; blank lines and lines starting with # are ignored. Exits non-zero
if any document failed, so a Kubernetes Job or CronJob reports the failure.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx

import pipeline


def from_dir(path: str) -> Iterable[Tuple[str, bytes]]:
    for p in pipeline.list_source_files(path):
        with open(p, "rb") as f:
            yield os.path.basename(p), f.read()


def read_url_list(path: str) -> List[str]:
    with open(path) as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]


def from_urls(urls: List[str], http: httpx.Client) -> Iterable[Tuple[str, Optional[bytes]]]:
    for url in urls:
        name = unquote(os.path.basename(urlparse(url).path)) or "document"
        try:
            r = http.get(url, follow_redirects=True, timeout=60)
            r.raise_for_status()
            yield name, r.content
        except httpx.HTTPError as e:
            print(f"FAILED   {name}: download error: {e}")
            yield name, None


def sync(docs: Iterable[Tuple[str, Optional[bytes]]], api: httpx.Client) -> dict:
    summary = {"indexed": 0, "unchanged": 0, "failed": 0}
    for name, content in docs:
        if content is None:
            summary["failed"] += 1
            continue
        try:
            r = api.post("/upload", files={"file": (name, content, "application/octet-stream")})
        except httpx.HTTPError as e:
            summary["failed"] += 1
            print(f"FAILED   {name}: {e}")
            continue
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200:
            summary["failed"] += 1
            print(f"FAILED   {name}: HTTP {r.status_code} {body.get('error', r.text[:200])}")
        elif body.get("unchanged"):
            summary["unchanged"] += 1
            print(f"same     {name}")
        else:
            summary["indexed"] += 1
            print(f"indexed  {name}: {body.get('chunks')} chunks")
    return summary


def main(argv: Optional[List[str]] = None, api: Optional[httpx.Client] = None,
         http: Optional[httpx.Client] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default=os.getenv("VB_API_URL", "http://127.0.0.1:8000"))
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", help="upload supported files from this directory")
    src.add_argument("--urls", help="file listing document URLs to download and upload")
    args = p.parse_args(argv)

    api = api or httpx.Client(base_url=args.api, timeout=600)  # large PDFs take a while to embed
    http = http or httpx.Client()
    docs = from_dir(args.dir) if args.dir else from_urls(read_url_list(args.urls), http)
    s = sync(docs, api)
    print(f"Done: {s['indexed']} indexed, {s['unchanged']} unchanged, {s['failed']} failed")
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
