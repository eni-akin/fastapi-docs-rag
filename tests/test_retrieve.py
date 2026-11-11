from pathlib import Path
from uuid import uuid4

import pytest

from fastapi_docs_rag.db import import_capture, migrate
from fastapi_docs_rag.retrieve import fuse, search


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
        ("x", 10, "unknown"),
    ],
)
def test_query_boundaries_are_validated_before_database(query, limit, mode):
    with pytest.raises(ValueError):
        search(object(), str(uuid4()), query, limit, mode)


def test_invalid_snapshot_uuid_is_rejected():
    with pytest.raises(ValueError, match="UUID"):
        search(object(), "not-a-uuid", "FastAPI")


def test_rrf_deduplicates_and_keeps_ranks_and_raw_scores():
    keyword = [{"chunk_id": "a", "score": 0.8}, {"chunk_id": "b", "score": 0.4}]
    vector = [
        {"chunk_id": "b", "score": 0.9, "similarity": 0.9, "distance": 0.1},
        {"chunk_id": "c", "score": 0.8, "similarity": 0.8, "distance": 0.2},
    ]
    rows = fuse(keyword, vector, 50)
    assert [row["chunk_id"] for row in rows] == ["b", "a", "c"]
    assert rows[0]["score"] == 1 / 62 + 1 / 61
    assert rows[0]["keyword_rank"] == 2 and rows[0]["vector_rank"] == 1
    assert rows[0]["keyword_score"] == 0.4 and rows[0]["vector_distance"] == 0.1
    assert rows[1]["vector_rank"] is None and rows[1]["vector_similarity"] is None
    assert rows[2]["keyword_rank"] is None and rows[2]["keyword_score"] is None


def test_rrf_ties_break_by_chunk_id_and_empty_keyword_is_valid():
    vector = [
        {"chunk_id": "b", "score": 0.9, "similarity": 0.9, "distance": 0.1},
        {"chunk_id": "a", "score": 0.8, "similarity": 0.8, "distance": 0.2},
    ]
    keyword = [{"chunk_id": "a", "score": 0.7}, {"chunk_id": "b", "score": 0.6}]
    assert [row["chunk_id"] for row in fuse(keyword, vector, 10)] == ["a", "b"]
    assert [row["chunk_id"] for row in fuse([], vector, 10)] == ["b", "a"]


def test_rrf_duplicate_candidate_uses_its_first_rank_only():
    row = {"chunk_id": "a", "score": 0.8}
    result = fuse([row, row], [], 10)
    assert len(result) == 1
    assert result[0]["score"] == 1 / 61
    assert result[0]["keyword_rank"] == 1


class _SnapshotConnection:
    def __init__(self, capability="vector_ready", profile=None):
        self.capability = capability
        self.profile = profile or {"embedding": {"model": "expected"}}

    def execute(self, statement, parameters):
        assert "FROM rag_snapshots" in statement
        return self

    def fetchone(self):
        return {"state": "ready", "capability": self.capability, "profile": self.profile}


def test_vector_rejects_keyword_snapshot_before_model_load():
    with pytest.raises(ValueError, match="vector-ready"):
        search(
            _SnapshotConnection(capability="keyword_only"), str(uuid4()), "FastAPI", mode="vector"
        )


def test_vector_rejects_incompatible_profile_before_encoding():
    class Embedder:
        profile = {"model": "other"}

        def encode(self, texts):
            raise AssertionError("Must not encode with a mismatched model")

    with pytest.raises(ValueError, match="profile"):
        search(_SnapshotConnection(), str(uuid4()), "FastAPI", mode="vector", embedder=Embedder())


def test_vector_rejects_token_overflow_from_embedder():
    class Embedder:
        profile = {"model": "expected"}

        def encode(self, texts):
            raise ValueError("Embedding input has 257 tokens; MiniLM limit is 256")

    with pytest.raises(ValueError, match="257 tokens"):
        search(
            _SnapshotConnection(), str(uuid4()), "word " * 300, mode="vector", embedder=Embedder()
        )


def test_capture_cli_requires_report_for_retained_artifacts(monkeypatch, capsys):
    from fastapi_docs_rag import cli

    monkeypatch.setattr("sys.argv", ["rag", "capture", "--retained-artifacts", "data"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "must be used together" in capsys.readouterr().err


def test_capture_cli_passes_retained_source(monkeypatch, capsys):
    from fastapi_docs_rag import cli

    seen = {}

    async def fake_capture(manifest, output, client, limits, **retained):
        seen.update(retained)
        return output / "report.json", {
            "status": "succeeded",
            "pages_succeeded": 1,
            "pages_failed": 0,
            "pages": [],
        }

    monkeypatch.setattr(cli, "capture", fake_capture)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "capture",
            "--retained-report",
            "old/report.json",
            "--retained-artifacts",
            "old",
        ],
    )
    assert cli.main() == 0
    assert seen == {
        "retained_report_path": Path("old/report.json"),
        "retained_artifact_dir": Path("old"),
    }
    assert "succeeded" in capsys.readouterr().out


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


def test_embed_snapshot_cli_uses_local_embedder(database, capture_factory, monkeypatch, capsys):
    import json

    from fastapi_docs_rag import cli, embed

    class Embedder:
        profile = {
            "model": "known-basis",
            "revision": "test",
            "pooling": "test",
            "license": "test",
            "dimension": 384,
            "normalization": "l2",
            "dtype": "float32",
            "max_input_tokens": 256,
            "batch_size": 32,
            "files": {"fixture": "known-basis"},
        }

        def encode(self, texts):
            return [[1.0, *([0.0] * 383)] for _ in texts]

    migrate(database)
    report, root = capture_factory()
    source = import_capture(database, report, root)["snapshot_id"]
    monkeypatch.setenv("RAG_DATABASE_URL", database.info.dsn)
    monkeypatch.setattr(embed, "load_embeddings", lambda model_dir: Embedder())
    monkeypatch.setattr("sys.argv", ["rag", "embed-snapshot", "--snapshot", source])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "ready" and result["encoded_inputs"] > 0


def test_exact_vector_order_ties_and_snapshot_scope(database, capture_factory):
    from fastapi_docs_rag.db import build_vector_snapshot

    class Embedder:
        profile = {
            "model": "known-basis",
            "revision": "test",
            "pooling": "test",
            "license": "test",
            "dimension": 384,
            "normalization": "l2",
            "dtype": "float32",
            "max_input_tokens": 256,
            "batch_size": 32,
            "files": {"fixture": "known-basis"},
        }

        def encode(self, texts):
            return [
                [1.0, *([0.0] * 383)] if "uniquefirstmarker" in text else [0.0, 1.0, *([0.0] * 382)]
                for text in texts
            ]

    migrate(database)
    report, root = capture_factory("uniquefirstmarker")
    first = import_capture(database, report, root)["snapshot_id"]
    report, root = capture_factory("uniquesecondmarker")
    second = import_capture(database, report, root)["snapshot_id"]
    first_vector = build_vector_snapshot(database, first, Embedder())["snapshot_id"]
    second_vector = build_vector_snapshot(database, second, Embedder())["snapshot_id"]
    rows = search(
        database, first_vector, "uniquefirstmarker", limit=50, mode="vector", embedder=Embedder()
    )
    assert rows and all(row["snapshot_id"] == first_vector for row in rows)
    assert [row["distance"] for row in rows] == sorted(row["distance"] for row in rows)
    assert rows[0]["distance"] == pytest.approx(0)
    assert rows[0]["similarity"] == pytest.approx(1)
    assert all(row["snapshot_id"] != second_vector for row in rows)
    for before, after in zip(rows, rows[1:], strict=False):
        if before["distance"] == after["distance"]:
            assert before["chunk_id"] < after["chunk_id"]
    hybrid = search(database, first_vector, "uniquefirstmarker", 50, "hybrid", Embedder())
    assert len(hybrid) <= 40
    assert len({row["chunk_id"] for row in hybrid}) == len(hybrid)
    assert all(row["snapshot_id"] == first_vector for row in hybrid)
