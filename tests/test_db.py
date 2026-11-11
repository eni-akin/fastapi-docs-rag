import json
from uuid import uuid4

import psycopg
import pytest

from fastapi_docs_rag import db
from fastapi_docs_rag.chunk import ChunkConfig


def test_migrations_are_repeatable_and_checked(database):
    assert db.migrate(database) == ["0001_keyword.sql", "0002_vectors.sql"]
    assert db.migrate(database) == []
    database.execute("UPDATE rag_schema_migrations SET sha256='modified'")
    with pytest.raises(ValueError, match="checksum"):
        db.migrate(database)


def test_import_reuses_complete_snapshot_and_profile_changes_create_new(database, capture_factory):
    db.migrate(database)
    report, root = capture_factory()
    first = db.import_capture(database, report, root)
    second = db.import_capture(database, report, root)
    assert first["snapshot_id"] == second["snapshot_id"]
    assert not first["reused"] and second["reused"]
    changed = db.import_capture(database, report, root, ChunkConfig(body_tokens=160))
    assert changed["snapshot_id"] != first["snapshot_id"]
    assert database.execute("SELECT count(*) AS n FROM rag_snapshots").fetchone()["n"] == 2
    assert database.execute("SELECT DISTINCT capability FROM rag_snapshots").fetchone() == {
        "capability": "keyword_only"
    }


def test_ready_content_and_snapshot_are_immutable(database, capture_factory):
    db.migrate(database)
    report, root = capture_factory()
    db.import_capture(database, report, root)
    for statement in [
        "UPDATE rag_snapshots SET chunk_count=1",
        "DELETE FROM rag_snapshots",
        "UPDATE rag_chunks SET text='changed'",
        "DELETE FROM rag_chunks",
        "UPDATE rag_documents SET title='changed'",
    ]:
        with pytest.raises(psycopg.Error, match="immutable"):
            database.execute(statement)


@pytest.mark.parametrize("with_existing", [False, True])
def test_failed_sql_import_rolls_back_all_rows(
    database, capture_factory, monkeypatch, with_existing
):
    db.migrate(database)
    if with_existing:
        baseline_report, baseline_root = capture_factory("existing evidence")
        db.import_capture(database, baseline_report, baseline_root)
    tables = ["rag_snapshots", "rag_documents", "rag_chunks"]
    before = {
        table: database.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
        for table in tables
    }
    report, root = capture_factory("failed replacement")
    original = db.chunk_document

    def invalid_chunk(document, config):
        result = original(document, config)
        result["chunks"][-1]["input_tokens"] = 257
        return result

    monkeypatch.setattr(db, "chunk_document", invalid_chunk)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.import_capture(database, report, root)
    for table in tables:
        assert (
            database.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == before[table]
        )


def test_document_and_chunk_snapshot_must_match(database, capture_factory):
    db.migrate(database)
    report, root = capture_factory()
    first = db.import_capture(database, report, root)
    document_id = database.execute(
        "SELECT id FROM rag_documents WHERE snapshot_id=%s", (first["snapshot_id"],)
    ).fetchone()["id"]
    with database.transaction():
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with database.transaction():
                # An existing document cannot be attached to a different snapshot.
                database.execute(
                    """
                    INSERT INTO rag_snapshots
                    SELECT %s, 'other', capability, 'building', manifest_hash, profile,
                           capture, document_count, chunk_count FROM rag_snapshots
                    WHERE id=%s
                """,
                    (uuid4(), first["snapshot_id"]),
                )
                database.execute(
                    """
                    INSERT INTO rag_chunks
                    (id, snapshot_id, document_id, chunk_key, evidence_key, text,
                     heading_path, section_anchor, variants, callout, source_spans,
                     partial_code, embedding_input, embedding_input_hash,
                     body_tokens, input_tokens, search_vector)
                    SELECT %s, s.id, %s, c.chunk_key, c.evidence_key, c.text,
                           c.heading_path, c.section_anchor, c.variants, c.callout, c.source_spans,
                           c.partial_code, c.embedding_input, c.embedding_input_hash,
                           c.body_tokens, c.input_tokens, c.search_vector
                    FROM rag_chunks c, rag_snapshots s WHERE s.fingerprint='other' LIMIT 1
                """,
                    (uuid4(), document_id),
                )


@pytest.mark.parametrize(
    "field, value",
    [
        ("status", "running"),
        ("manifest_hash", "modified"),
        ("pages_succeeded", 2),
    ],
)
def test_invalid_report_is_rejected_without_a_database(capture_factory, field, value):
    report, root = capture_factory()
    data = json.loads(report.read_text())
    data[field] = value
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        db.load_capture(report, root)


def test_corrupt_raw_and_unsafe_paths_are_rejected(capture_factory):
    report, root = capture_factory()
    data = json.loads(report.read_text())
    raw = root / data["pages"][0]["raw_path"]
    raw.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        db.load_capture(report, root)
    data["pages"][0]["raw_path"] = "../outside.html"
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="path"):
        db.load_capture(report, root)


def test_modified_parsed_document_is_rejected(capture_factory):
    report, root = capture_factory()
    data = json.loads(report.read_text())
    parsed = root / data["pages"][0]["parsed_path"]
    document = json.loads(parsed.read_text())
    document["blocks"][1]["text"] = "invented source evidence"
    parsed.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="differs"):
        db.load_capture(report, root)


def test_symlink_escape_is_rejected(capture_factory, tmp_path):
    report, root = capture_factory()
    data = json.loads(report.read_text())
    raw = root / data["pages"][0]["raw_path"]
    outside = tmp_path / "outside.html"
    outside.write_bytes(raw.read_bytes())
    raw.unlink()
    raw.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        db.load_capture(report, root)


def test_storage_cli_uses_real_database(database, capture_factory, monkeypatch, capsys):
    from fastapi_docs_rag import cli

    monkeypatch.setenv("RAG_DATABASE_URL", database.info.dsn)
    monkeypatch.setattr("sys.argv", ["rag", "migrate"])
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out)["applied"] == [
        "0001_keyword.sql",
        "0002_vectors.sql",
    ]
    report, root = capture_factory()
    monkeypatch.setattr(
        "sys.argv", ["rag", "import-capture", "--report", str(report), "--artifacts", str(root)]
    )
    assert cli.main() == 0
    first = json.loads(capsys.readouterr().out)
    assert cli.main() == 0
    second = json.loads(capsys.readouterr().out)
    assert first["snapshot_id"] == second["snapshot_id"]
    assert second["reused"]


def test_missing_database_setting_has_clear_diagnostic(monkeypatch, capsys):
    from fastapi_docs_rag import cli

    monkeypatch.delenv("RAG_DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["rag", "migrate"])
    assert cli.main() == 1
    assert "Set RAG_DATABASE_URL" in capsys.readouterr().err
