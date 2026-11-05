from uuid import uuid4

import pytest

from fastapi_docs_rag.db import import_capture, migrate
from fastapi_docs_rag.retrieve import search


def test_keyword_search_is_scoped_traceable_and_stable(database, capture_factory):
    migrate(database)
    report, root = capture_factory("uniquefirstmarker")
    first = import_capture(database, report, root)
    report, root = capture_factory("uniquesecondmarker")
    second = import_capture(database, report, root)
    results = search(database, first["snapshot_id"], "uniquefirstmarker")
    assert results
    assert results == search(database, first["snapshot_id"], "uniquefirstmarker")
    assert all(r["snapshot_id"] == first["snapshot_id"] for r in results)
    assert search(database, first["snapshot_id"], "uniquesecondmarker") == []
    assert search(database, second["snapshot_id"], "uniquefirstmarker") == []
    for result in results:
        assert result["score"] > 0 and result["input_tokens"] <= 256
        doc = database.execute(
            "SELECT document FROM rag_documents WHERE id=%s", (result["document_id"],)
        ).fetchone()["document"]
        spans = result["source_spans"]
        assert result["text"] == "\n\n".join(
            doc["blocks"][s["block_index"]]["text"][s["start"] : s["end"]] for s in spans
        )
        assert result["url"].startswith(doc["url"])


def test_empty_results_and_sql_like_text_are_safe(database, capture_factory):
    migrate(database)
    report, root = capture_factory()
    snapshot = import_capture(database, report, root)["snapshot_id"]
    assert search(database, snapshot, "unfindablewordx") == []
    assert search(database, snapshot, "...") == []
    search(database, snapshot, "'; DROP TABLE rag_snapshots; --")
    assert database.execute("SELECT count(*) AS n FROM rag_snapshots").fetchone()["n"] == 1


@pytest.mark.parametrize(
    "query, limit, mode",
    [
        ("", 10, "keyword"),
        ("  ", 10, "keyword"),
        ("x" * 2001, 10, "keyword"),
        ("x", 0, "keyword"),
        ("x", 51, "keyword"),
        ("x", True, "keyword"),
        ("x", 10, "vector"),
    ],
)
def test_query_boundaries_are_validated_before_database(query, limit, mode):
    with pytest.raises(ValueError):
        search(object(), str(uuid4()), query, limit, mode)


def test_invalid_snapshot_uuid_is_rejected():
    with pytest.raises(ValueError, match="UUID"):
        search(object(), "not-a-uuid", "FastAPI")


def test_unknown_and_building_snapshot_are_rejected(database, capture_factory):
    migrate(database)
    with pytest.raises(ValueError, match="Unknown"):
        search(database, str(uuid4()), "FastAPI")
    report, root = capture_factory()
    first = import_capture(database, report, root)
    building = uuid4()
    database.execute(
        """
        INSERT INTO rag_snapshots
        SELECT %s, 'unpublished', capability, 'building', manifest_hash, profile,
               capture, document_count, chunk_count FROM rag_snapshots WHERE id=%s
    """,
        (building, first["snapshot_id"]),
    )
    with pytest.raises(ValueError, match="not ready"):
        search(database, str(building), "FastAPI")


def test_search_cli_json_and_readable_output(database, capture_factory, monkeypatch, capsys):
    import json

    from fastapi_docs_rag import cli

    migrate(database)
    report, root = capture_factory()
    snapshot = import_capture(database, report, root)["snapshot_id"]
    monkeypatch.setenv("RAG_DATABASE_URL", database.info.dsn)
    arguments = [
        "rag",
        "search",
        "--mode",
        "keyword",
        "--snapshot",
        snapshot,
        "--query",
        "FastAPI",
        "--limit",
        "1",
    ]
    monkeypatch.setattr("sys.argv", [*arguments, "--json"])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["snapshot_id"] == snapshot
    assert len(result["results"]) == 1
    assert result["results"][0]["source_spans"]
    monkeypatch.setattr("sys.argv", arguments)
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert snapshot in output and "source spans:" in output and "partial code:" in output
