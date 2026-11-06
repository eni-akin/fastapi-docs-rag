import asyncio
import os
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from fastapi_docs_rag.fetch import FetchLimits
from fastapi_docs_rag.ingest import capture


@pytest.fixture
def database():
    dsn = os.environ.get("RAG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set RAG_TEST_DATABASE_URL to run real PostgreSQL integration tests")
    # Only this fixture's freshly generated database may be dropped.
    name = "rag_test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with psycopg.connect(
                make_conninfo(dsn, dbname=name), autocommit=True, row_factory=dict_row
            ) as connection:
                yield connection
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def capture_factory(tmp_path):
    def create(marker="Hello World"):
        root = tmp_path / uuid4().hex
        root.mkdir()
        manifest = root / "manifest.json"
        import json

        manifest.write_text(
            json.dumps(
                {
                    "version": 1,
                    "pages": [
                        {
                            "url": "https://fastapi.tiangolo.com/tutorial/first-steps/",
                            "expected_title": "First Steps",
                            "expected_code": "FastAPI",
                        }
                    ],
                }
            )
        )
        html = (Path(__file__).parent / "fixtures/first-steps.html").read_bytes()
        html = html.replace(b"Hello World", marker.encode())

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, content=html, headers={"content-type": "text/html"}
                    )
                )
            ) as client:
                return await capture(manifest, root, client, FetchLimits(pause=0))

        path, _ = asyncio.run(run())
        return path, root

    return create
