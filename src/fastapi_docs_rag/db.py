"""Transactional keyword snapshots and checksum-verified capture import."""

import hashlib
import json
import os
import re
from importlib.resources import files
from pathlib import Path
from uuid import uuid4, uuid5

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fastapi_docs_rag.chunk import ChunkConfig, chunk_document
from fastapi_docs_rag.manifest import canonical_url, json_hash
from fastapi_docs_rag.parse import PARSER_VERSION, parse_page, validate_page

KEYWORD_PROFILE = {
    "version": "1",
    "configuration": "simple",
    "heading_weight": "A",
    "body_weight": "B",
}


def connect_database():
    dsn = os.environ.get("RAG_DATABASE_URL")
    if not dsn:
        raise ValueError("Set RAG_DATABASE_URL to the project PostgreSQL connection")
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5)


def migrate(connection) -> list[str]:
    applied = []
    migrations = sorted(files("fastapi_docs_rag").joinpath("sql").iterdir(), key=lambda p: p.name)
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(610240001)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS rag_schema_migrations (
                name text PRIMARY KEY, sha256 text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        existing = {
            row["name"]: row["sha256"]
            for row in connection.execute("SELECT name, sha256 FROM rag_schema_migrations")
        }
        known = {path.name for path in migrations if path.name.endswith(".sql")}
        if set(existing) - known:
            raise ValueError("Database has migrations newer than this application")
        for path in migrations:
            if not path.name.endswith(".sql"):
                continue
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if path.name in existing:
                if existing[path.name] != digest:
                    raise ValueError(f"Applied migration checksum changed: {path.name}")
                continue
            connection.execute(content.decode("utf-8"))
            connection.execute(
                "INSERT INTO rag_schema_migrations(name, sha256) VALUES (%s, %s)",
                (path.name, digest),
            )
            applied.append(path.name)
    return applied


def _artifact(root: Path, relative: str, expected: str) -> Path:
    if relative != expected:
        raise ValueError("Capture artifact path does not match its content hash")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Capture artifact escapes the supplied artifact root")
    return path


def load_capture(report_path: Path, artifact_root: Path) -> tuple[dict, list[dict]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        return _validate_capture(report, artifact_root)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed capture report or parsed document") from error


def _validate_capture(report: dict, artifact_root: Path) -> tuple[dict, list[dict]]:
    if report.get("status") != "succeeded" or report.get("parser_version") != PARSER_VERSION:
        raise ValueError("Import requires a complete capture with the current parser version")
    manifest = report["manifest"]
    expected_pages = manifest["pages"]
    pages = report["pages"]
    if (
        manifest["version"] != 1
        or report["manifest_hash"] != json_hash(manifest)
        or len(pages) != len(expected_pages)
        or not pages
    ):
        raise ValueError("Capture manifest hash or page count mismatch")
    if report["pages_succeeded"] != len(pages) or report["pages_failed"] != 0:
        raise ValueError("Capture completion counters do not match the complete page set")
    urls = [canonical_url(page["url"]) for page in expected_pages]
    if urls != sorted(set(urls)):
        raise ValueError("Capture manifest URLs must be unique and sorted")
    documents = []
    for expected, page in zip(expected_pages, pages, strict=True):
        if page.get("status") != "succeeded" or page["url"] != expected["url"]:
            raise ValueError("Incomplete or mismatched capture page")
        for key in ("raw_hash", "content_hash"):
            if not re.fullmatch("[0-9a-f]{64}", page[key]):
                raise ValueError(f"Invalid capture {key}")
        raw_path = _artifact(artifact_root, page["raw_path"], f"raw/{page['raw_hash']}.html")
        parsed_path = _artifact(
            artifact_root, page["parsed_path"], f"parsed/{page['content_hash']}.json"
        )
        raw = raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != page["raw_hash"]:
            raise ValueError("Raw artifact checksum mismatch")
        if len(raw) != page["bytes"]:
            raise ValueError("Capture byte count mismatch")
        document = json.loads(parsed_path.read_text(encoding="utf-8"))
        replayed = parse_page(raw, canonical_url(page["final_url"]))
        if document != replayed or document.get("content_hash") != page["content_hash"]:
            raise ValueError("Parsed artifact differs from its checksum-verified source")
        validate_page(document, expected)
        for key, count in {
            "blocks": len(document["blocks"]),
            "sections": sum(b["type"] == "heading" for b in document["blocks"]),
            "code_blocks": sum(b["type"] == "code" for b in document["blocks"]),
        }.items():
            if page[key] != count:
                raise ValueError(f"Capture {key} count mismatch")
        documents.append(document)
    if len({document["url"] for document in documents}) != len(documents):
        raise ValueError("Multiple requested pages resolve to the same document")
    return report, documents


def import_capture(
    connection, report_path: Path, artifact_root: Path, config: ChunkConfig | None = None
) -> dict:
    report, documents = load_capture(report_path, artifact_root)
    prepared = [chunk_document(document, config) for document in documents]
    profile = {**prepared[0]["profile"], "keyword_search": KEYWORD_PROFILE}
    fingerprint = json_hash(
        {
            "manifest_hash": report["manifest_hash"],
            "profile": profile,
            "documents": sorted((d["url"], d["content_hash"]) for d in documents),
        }
    )
    chunk_count = sum(len(result["chunks"]) for result in prepared)
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(610240002)")
        existing = connection.execute(
            "SELECT id, state, document_count, chunk_count FROM rag_snapshots WHERE fingerprint=%s",
            (fingerprint,),
        ).fetchone()
        if existing:
            if existing["state"] != "ready":
                raise ValueError("An incomplete snapshot already owns this corpus fingerprint")
            return {
                "snapshot_id": str(existing["id"]),
                "reused": True,
                "state": existing["state"],
                "document_count": existing["document_count"],
                "chunk_count": existing["chunk_count"],
            }
        snapshot_id = uuid4()
        connection.execute(
            """
            INSERT INTO rag_snapshots
            (id, fingerprint, state, manifest_hash, profile, capture, document_count, chunk_count)
            VALUES (%s, %s, 'building', %s, %s, %s, %s, %s)
        """,
            (
                snapshot_id,
                fingerprint,
                report["manifest_hash"],
                Jsonb(profile),
                Jsonb(report),
                len(documents),
                chunk_count,
            ),
        )
        for document, result, page in zip(documents, prepared, report["pages"], strict=True):
            document_id = uuid5(snapshot_id, document["url"])
            connection.execute(
                """
                INSERT INTO rag_documents
                (id, snapshot_id, source_url, title, content_hash, raw_hash, document)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    document_id,
                    snapshot_id,
                    document["url"],
                    document["title"],
                    document["content_hash"],
                    page["raw_hash"],
                    Jsonb(document),
                ),
            )
            for chunk in result["chunks"]:
                connection.execute(
                    """
                    INSERT INTO rag_chunks (
                        id, snapshot_id, document_id, chunk_key, evidence_key, text,
                        heading_path, section_anchor, variants, callout, source_spans,
                        partial_code, embedding_input, embedding_input_hash,
                        body_tokens, input_tokens, search_vector
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        setweight(to_tsvector('simple', %s), 'A') ||
                        setweight(to_tsvector('simple', %s), 'B')
                    )
                """,
                    (
                        uuid5(snapshot_id, chunk["chunk_key"]),
                        snapshot_id,
                        document_id,
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
                        document["title"] + " " + " ".join(chunk["heading_path"]),
                        chunk["text"],
                    ),
                )
        actual = connection.execute(
            "SELECT count(*) AS count FROM rag_chunks WHERE snapshot_id=%s", (snapshot_id,)
        ).fetchone()["count"]
        if actual != chunk_count:
            raise ValueError("Snapshot row count does not match the complete chunk set")
        connection.execute("UPDATE rag_snapshots SET state='ready' WHERE id=%s", (snapshot_id,))
    return {
        "snapshot_id": str(snapshot_id),
        "reused": False,
        "state": "ready",
        "document_count": len(documents),
        "chunk_count": chunk_count,
    }
