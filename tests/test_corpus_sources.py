"""
Tests for switching between the two curated demo corpora.

The bug this file exists to catch: seeding and fetching used to be "write if
missing", so switching from the 6-paper sample set to the 30-paper arXiv set
(or back) left both on disk at once - a corpus of 36 mixed papers instead of
exactly the 30 requested. Every endpoint here is exercised as a *switch*, and
each assertion is about the corpus directory's exact final contents, not just
that a request returned 200.

The arXiv fetch itself is monkeypatched to avoid a real network call in the
test suite; what matters here is what the server does with the result, not
the HTTP fetch.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rpra import server
from rpra.arxiv_corpus import known_slugs as arxiv_known_slugs
from rpra.sample_corpus import known_slugs as sample_known_slugs


@pytest.fixture
def isolated_corpus(tmp_path, monkeypatch):
    """Point the server at an empty, disposable corpus directory."""
    corpus_dir = tmp_path / "papers"
    monkeypatch.setattr(server.current_settings.storage, "corpus_input_path", str(corpus_dir))
    monkeypatch.setattr(server.current_settings.storage, "output_path", str(tmp_path / "out"))
    monkeypatch.setenv("RPRA_SEED_CORPUS", "0")  # no auto-seed noise in these tests
    return corpus_dir


@pytest.fixture
def fake_arxiv_fetch(monkeypatch):
    """
    Replace the real network download with an instant local write.

    Writes a minimal placeholder PDF for every paper in the real arXiv paper
    list, so known_slugs() and missing_papers() - which read that same list -
    stay accurate without a single HTTP request.
    """
    import rpra.arxiv_corpus as arxiv_module

    def fake_fetch_corpus(out_dir, on_progress=None, delay_seconds=0.0):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for index, paper in enumerate(arxiv_module.PAPERS, start=1):
            target = out_dir / f"{paper['slug']}.pdf"
            if not target.exists() or target.stat().st_size <= 10_000:
                # Must clear _is_complete()'s real 10 KB floor, or every
                # "already downloaded" check below still reports it missing.
                target.write_bytes(b"%PDF-1.4 fake\n" + b"0" * 20_000)
            if on_progress:
                on_progress(index, len(arxiv_module.PAPERS), paper["slug"], True)
        return {
            "counts": {
                "requested": len(arxiv_module.PAPERS),
                "available": len(arxiv_module.PAPERS),
                "failed": 0,
                "downloaded_this_run": len(arxiv_module.PAPERS),
            }
        }

    monkeypatch.setattr(arxiv_module, "fetch_corpus", fake_fetch_corpus)
    return fake_fetch_corpus


def wait_until_idle(client: TestClient, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get("/api/status").json()
        if status["status"] != "running":
            return status
        time.sleep(0.05)
    raise AssertionError("background job did not finish in time")


# ---------------------------------------------------------------------------
# The two curated sets do not overlap
# ---------------------------------------------------------------------------


def test_sample_and_arxiv_slugs_are_disjoint():
    """
    _purge_known relies on the two sets never sharing a filename - otherwise
    switching to one would also silently delete papers belonging to both.
    """
    assert sample_known_slugs() & arxiv_known_slugs() == set()
    assert len(sample_known_slugs()) == 6
    assert len(arxiv_known_slugs()) == 30


# ---------------------------------------------------------------------------
# Switching, not mixing
# ---------------------------------------------------------------------------


def test_seed_writes_exactly_the_sample_set(isolated_corpus):
    with TestClient(server.app) as client:
        body = client.post("/api/corpus/seed").json()
        assert body["pdf_count"] == 6

    names = {p.stem for p in isolated_corpus.glob("*.pdf")}
    assert names == sample_known_slugs()


def test_fetch_arxiv_purges_a_pre_existing_sample_corpus(isolated_corpus, fake_arxiv_fetch):
    """
    The scenario a user actually hit: 6 sample papers already on disk (from a
    previous session, or an auto-seeded restart), then "Load 30 (arXiv)" is
    clicked. The result must be exactly 30 papers, not 36.
    """
    with TestClient(server.app) as client:
        client.post("/api/corpus/seed")
        assert client.get("/api/status").json()["pdf_count"] == 6

        client.post("/api/corpus/fetch-arxiv")
        status = wait_until_idle(client)
        assert status["pdf_count"] == 30

    names = {p.stem for p in isolated_corpus.glob("*.pdf")}
    assert names == arxiv_known_slugs()


def test_seed_purges_a_pre_existing_arxiv_corpus(isolated_corpus, fake_arxiv_fetch):
    """The reverse switch: arXiv loaded, then explicitly switching to sample."""
    with TestClient(server.app) as client:
        client.post("/api/corpus/fetch-arxiv")
        wait_until_idle(client)
        assert client.get("/api/status").json()["pdf_count"] == 30

        client.post("/api/corpus/seed")
        assert client.get("/api/status").json()["pdf_count"] == 6

    names = {p.stem for p in isolated_corpus.glob("*.pdf")}
    assert names == sample_known_slugs()


def test_a_users_own_upload_survives_switching_corpora(isolated_corpus, fake_arxiv_fetch):
    """
    Only the two curated sets' own filenames are ever purged - a paper a user
    uploaded under an arbitrary name must never be silently deleted by
    switching between the sample and arXiv demo corpora.
    """
    isolated_corpus.mkdir(parents=True, exist_ok=True)
    (isolated_corpus / "my_own_paper.pdf").write_bytes(b"%PDF-1.4 mine\n" + b"0" * 200)

    with TestClient(server.app) as client:
        client.post("/api/corpus/seed")
        client.post("/api/corpus/fetch-arxiv")
        wait_until_idle(client)

    names = {p.stem for p in isolated_corpus.glob("*.pdf")}
    assert "my_own_paper" in names
    assert names == arxiv_known_slugs() | {"my_own_paper"}


def test_fetch_arxiv_is_cheap_when_already_loaded(isolated_corpus, fake_arxiv_fetch):
    """Re-requesting an already-loaded corpus reports nothing outstanding."""
    with TestClient(server.app) as client:
        client.post("/api/corpus/fetch-arxiv")
        wait_until_idle(client)

        body = client.post("/api/corpus/fetch-arxiv").json()
        assert body["to_download"] == 0
        wait_until_idle(client)

    names = {p.stem for p in isolated_corpus.glob("*.pdf")}
    assert names == arxiv_known_slugs()


# ---------------------------------------------------------------------------
# Startup must never block on a two-minute network fetch
# ---------------------------------------------------------------------------


def test_arxiv_seed_mode_does_not_block_startup(isolated_corpus, fake_arxiv_fetch, monkeypatch):
    """
    RPRA_SEED_CORPUS=arxiv fetches the full corpus automatically after every
    restart, but that fetch takes about two minutes against the real arXiv
    endpoint. Doing it synchronously in the startup hook would fail a
    platform's health check on every single restart. It must return
    immediately and finish in the background instead.
    """
    monkeypatch.setenv("RPRA_SEED_CORPUS", "arxiv")

    start = time.time()
    with TestClient(server.app) as client:
        elapsed = time.time() - start
        assert elapsed < 5.0, "startup blocked on the corpus fetch"

        status = wait_until_idle(client, timeout=10.0)
        assert status["pdf_count"] == 30

    names = {p.stem for p in isolated_corpus.glob("*.pdf")}
    assert names == arxiv_known_slugs()


def test_arxiv_seed_mode_does_nothing_if_papers_already_present(isolated_corpus, monkeypatch):
    """Auto-seeding must never overwrite a corpus that is already populated."""
    isolated_corpus.mkdir(parents=True, exist_ok=True)
    (isolated_corpus / "existing.pdf").write_bytes(b"%PDF-1.4\n" + b"0" * 200)
    monkeypatch.setenv("RPRA_SEED_CORPUS", "arxiv")

    with TestClient(server.app) as client:
        assert client.get("/api/status").json()["pdf_count"] == 1
