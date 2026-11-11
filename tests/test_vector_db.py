import math
from uuid import uuid4

import psycopg
import pytest
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from fastapi_docs_rag import db


class StubEmbeddings:
    def __init__(self, model="stub"):
        self.profile = {
            "model": model,
            "revision": "test",
            "files": {"weights": model},
            "pooling": "mean",
            "normalization": "l2",
            "dtype": "float32",
            "dimension": 384,
            "max_input_tokens": 256,
            "batch_size": 32,
            "license": "Apache-2.0",
        }
        self.calls = []

    def encode(self, texts):
        self.calls.append(list(texts))
        return [[1.0] + [0.0] * 383 for _ in texts]


def _keyword(database, capture_factory, marker="Hello World"):
    db.migrate(database)
    report, root = capture_factory(marker)
    return db.import_capture(database, report, root)["snapshot_id"]


def _counts(database):
    return tuple(
        database.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
        for table in ("rag_snapshots", "rag_documents", "rag_chunks")
    )


def test_vector_build_is_complete_immutable_and_reuses_identical_snapshot(
    database, capture_factory
):
    source = _keyword(database, capture_factory)
    source_before = database.execute(
        "SELECT count(*) AS n FROM rag_chunks WHERE snapshot_id=%s AND embedding IS NULL", (source,)
    ).fetchone()["n"]
    embedder = StubEmbeddings()
    original_encode = embedder.encode

    def checked_encode(texts):
        assert database.info.transaction_status == TransactionStatus.IDLE
        assert len(texts) <= 32
        return original_encode(texts)

    embedder.encode = checked_encode
    result = db.build_vector_snapshot(database, source, embedder)
    assert result["chunk_count"] == source_before
    assert (
        result["document_count"]
        == database.execute(
            "SELECT count(*) AS n FROM rag_documents WHERE snapshot_id=%s", (source,)
        ).fetchone()["n"]
    )
    assert result["encoded_inputs"] == sum(map(len, embedder.calls))
    assert result["reused_inputs"] == 0
    assert db.build_vector_snapshot(database, source, embedder)["reused"]
    assert sum(map(len, embedder.calls)) == result["encoded_inputs"]
    assert (
        database.execute(
            "SELECT count(*) AS n FROM rag_chunks WHERE snapshot_id=%s AND embedding IS NULL",
            (source,),
        ).fetchone()["n"]
        == source_before
    )
    vector_id = result["snapshot_id"]
    assert not database.execute(
        """
        SELECT 1 FROM rag_chunks a JOIN rag_chunks b ON a.id=b.id
        WHERE a.snapshot_id=%s AND b.snapshot_id=%s
        """,
        (source, vector_id),
    ).fetchone()
    assert (
        database.execute(
            "SELECT count(*) AS n FROM rag_chunks WHERE snapshot_id=%s AND embedding IS NOT NULL",
            (vector_id,),
        ).fetchone()["n"]
        == source_before
    )
    with pytest.raises(psycopg.Error, match="immutable"):
        database.execute("UPDATE rag_chunks SET text='changed' WHERE snapshot_id=%s", (vector_id,))
    with pytest.raises(psycopg.Error, match="immutable"):
        database.execute("DELETE FROM rag_documents WHERE snapshot_id=%s", (vector_id,))


def test_compatible_input_reuse_and_profile_invalidation(database, capture_factory):
    first = _keyword(database, capture_factory)
    first_embedder = StubEmbeddings()
    first_result = db.build_vector_snapshot(database, first, first_embedder)
    second = _keyword(database, capture_factory, "Different World")
    second_embedder = StubEmbeddings()
    second_result = db.build_vector_snapshot(database, second, second_embedder)
    assert second_result["snapshot_id"] != first_result["snapshot_id"]
    assert second_result["reused_inputs"] > 0
    assert second_result["encoded_inputs"] > 0
    changed = db.build_vector_snapshot(database, second, StubEmbeddings("other-model"))
    assert changed["reused_inputs"] == 0
    assert changed["encoded_inputs"] > 0


def test_bad_input_or_encoder_cannot_publish(database, capture_factory):
    source = _keyword(database, capture_factory)
    before = _counts(database)
    broken = StubEmbeddings()
    broken.encode = lambda texts: [[math.nan] + [0.0] * 383 for _ in texts]
    with pytest.raises(ValueError, match="finite"):
        db.build_vector_snapshot(database, source, broken)
    assert _counts(database) == before
    with pytest.raises(ValueError, match="ready keyword"):
        db.build_vector_snapshot(database, uuid4(), StubEmbeddings())


def test_failed_publication_rolls_back_candidate_rows(database, capture_factory):
    source = _keyword(database, capture_factory)
    before = _counts(database)
    database.execute("""
        CREATE FUNCTION fail_vector_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM rag_snapshots WHERE id=NEW.snapshot_id
                       AND capability='vector_ready') THEN
                RAISE EXCEPTION 'forced vector publication failure';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER fail_vector_chunk BEFORE INSERT ON rag_chunks
        FOR EACH ROW EXECUTE FUNCTION fail_vector_chunk();
    """)
    with pytest.raises(psycopg.Error, match="forced vector publication failure"):
        db.build_vector_snapshot(database, source, StubEmbeddings())
    assert _counts(database) == before


@pytest.mark.parametrize(
    "profile", [None, {}, {"embedding": {}}, {"embedding": {"dimension": 384}}]
)
def test_direct_ready_insert_rejects_missing_content_or_profile(database, profile):
    db.migrate(database)
    with pytest.raises(psycopg.Error, match="incomplete|profile"):
        database.execute(
            """
            INSERT INTO rag_snapshots
            (id, fingerprint, capability, state, manifest_hash, profile, capture,
             document_count, chunk_count)
            VALUES (%s, %s, 'vector_ready', 'ready', 'manifest', %s, '{}'::jsonb, 1, 1)
            """,
            (uuid4(), uuid4().hex, Jsonb(profile)),
        )


def test_readiness_rejects_missing_and_nonunit_vectors(database, capture_factory):
    source = _keyword(database, capture_factory)
    result = db.build_vector_snapshot(database, source, StubEmbeddings())
    row = database.execute(
        "SELECT * FROM rag_snapshots WHERE id=%s", (result["snapshot_id"],)
    ).fetchone()
    candidate = uuid4()
    database.execute(
        """
        INSERT INTO rag_snapshots
        (id, fingerprint, capability, state, manifest_hash, profile, capture,
         document_count, chunk_count)
        VALUES (%s, %s, 'vector_ready', 'building', %s, %s, %s, %s, %s)
        """,
        (
            candidate,
            uuid4().hex,
            row["manifest_hash"],
            Jsonb(row["profile"]),
            Jsonb(row["capture"]),
            1,
            1,
        ),
    )
    with pytest.raises(psycopg.Error, match="incomplete"):
        database.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (candidate,))
    document = database.execute(
        "SELECT * FROM rag_documents WHERE snapshot_id=%s LIMIT 1", (result["snapshot_id"],)
    ).fetchone()
    new_document_id = uuid4()
    database.execute(
        """
        INSERT INTO rag_documents
        (id, snapshot_id, source_url, title, content_hash, raw_hash, document)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            new_document_id,
            candidate,
            document["source_url"],
            document["title"],
            document["content_hash"],
            document["raw_hash"],
            Jsonb(document["document"]),
        ),
    )
    chunk = database.execute(
        "SELECT * FROM rag_chunks WHERE document_id=%s LIMIT 1", (document["id"],)
    ).fetchone()
    database.execute(
        """
        INSERT INTO rag_chunks
        (id, snapshot_id, document_id, chunk_key, evidence_key, text, heading_path,
         section_anchor, variants, callout, source_spans, partial_code,
         embedding_input, embedding_input_hash, body_tokens, input_tokens, search_vector)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            candidate,
            new_document_id,
            chunk["chunk_key"],
            chunk["evidence_key"],
            chunk["text"],
            Jsonb(chunk["heading_path"]),
            chunk["section_anchor"],
            Jsonb(chunk["variants"]),
            Jsonb(chunk["callout"]),
            Jsonb(chunk["source_spans"]),
            chunk["partial_code"],
            chunk["embedding_input"],
            chunk["embedding_input_hash"],
            chunk["body_tokens"],
            chunk["input_tokens"],
            chunk["search_vector"],
        ),
    )
    with pytest.raises(psycopg.Error, match="embeddings"):
        database.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (candidate,))
    database.execute(
        "UPDATE rag_chunks SET embedding=%s::vector WHERE snapshot_id=%s",
        ("[2," + ",".join("0" for _ in range(383)) + "]", candidate),
    )
    with pytest.raises(psycopg.Error, match="embeddings"):
        database.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (candidate,))
    database.execute(
        "UPDATE rag_chunks SET embedding=%s::vector WHERE snapshot_id=%s",
        ("[" + ",".join("0" for _ in range(384)) + "]", candidate),
    )
    with pytest.raises(psycopg.Error, match="embeddings"):
        database.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (candidate,))
    database.execute(
        "UPDATE rag_chunks SET embedding=%s::vector WHERE snapshot_id=%s",
        ("[1," + ",".join("0" for _ in range(383)) + "]", candidate),
    )
    database.execute(
        "UPDATE rag_snapshots SET profile=%s WHERE id=%s",
        (Jsonb({"embedding": {"dimension": 384}}), candidate),
    )
    with pytest.raises(psycopg.Error, match="profile"):
        database.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (candidate,))
    database.execute("UPDATE rag_snapshots SET capability='keyword_only' WHERE id=%s", (candidate,))
    with pytest.raises(psycopg.Error, match="cannot contain embeddings"):
        database.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (candidate,))
