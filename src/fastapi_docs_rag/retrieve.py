"""Inspectable retrieval from one explicit, ready documentation snapshot."""

from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi_docs_rag.embed import DEFAULT_MODEL_DIR, load_embeddings, validate_vector

SOURCE_FIELDS = """
    c.id::text AS chunk_id, c.snapshot_id::text AS snapshot_id,
    d.id::text AS document_id, d.source_url, d.title,
    d.content_hash AS document_content_hash,
    c.evidence_key, c.text, c.heading_path, c.section_anchor, c.variants,
    c.callout, c.source_spans, c.partial_code, c.body_tokens, c.input_tokens
"""


def _with_urls(rows):
    for row in rows:
        anchor = row["section_anchor"]
        row["url"] = row["source_url"] + ("#" + quote(anchor, safe="-_") if anchor else "")
    return rows


def _keyword(connection, snapshot, query, limit):
    rows = connection.execute(
        f"""
        WITH question AS (SELECT websearch_to_tsquery('simple', %s) AS query)
        SELECT {SOURCE_FIELDS}, ts_rank_cd(c.search_vector, question.query) AS score
        FROM rag_chunks c
        JOIN rag_documents d ON d.id=c.document_id AND d.snapshot_id=c.snapshot_id
        CROSS JOIN question
        WHERE c.snapshot_id=%s AND c.search_vector @@ question.query
        ORDER BY score DESC, c.id ASC
        LIMIT %s
        """,
        (query, snapshot, limit),
    ).fetchall()
    return _with_urls(rows)


def _vector(connection, snapshot, vector, limit):
    # pgvector accepts a bound text value; the cast is fixed SQL, never user input.
    encoded = "[" + ",".join(str(value) for value in validate_vector(vector)) + "]"
    rows = connection.execute(
        f"""
        SELECT {SOURCE_FIELDS}, c.embedding <=> %s::vector AS distance
        FROM rag_chunks c
        JOIN rag_documents d ON d.id=c.document_id AND d.snapshot_id=c.snapshot_id
        WHERE c.snapshot_id=%s AND c.embedding IS NOT NULL
        ORDER BY distance ASC, c.id ASC
        LIMIT %s
        """,
        (encoded, snapshot, limit),
    ).fetchall()
    for row in rows:
        row["similarity"] = 1.0 - row["distance"]  # cosine similarity, not answerability
        row["score"] = row["similarity"]
    return _with_urls(rows)


def fuse(keyword_rows, vector_rows, limit):
    """Fuse at most 20 candidates per source with hand-checkable RRF ranks."""
    results = {}
    for field, rows in (("keyword", keyword_rows), ("vector", vector_rows)):
        for rank, row in enumerate(rows, start=1):
            chunk_id = row["chunk_id"]
            if chunk_id in results and results[chunk_id][f"{field}_rank"] is not None:
                continue
            result = results.setdefault(
                chunk_id,
                {
                    **row,
                    "score": 0.0,
                    "keyword_rank": None,
                    "vector_rank": None,
                    "keyword_score": None,
                    "vector_distance": None,
                    "vector_similarity": None,
                },
            )
            result["score"] += 1 / (60 + rank)
            result[f"{field}_rank"] = rank
            if field == "keyword":
                result["keyword_score"] = row["score"]
            else:
                result["vector_distance"] = row["distance"]
                result["vector_similarity"] = row["similarity"]
    return sorted(results.values(), key=lambda row: (-row["score"], row["chunk_id"]))[:limit]


def search(
    connection,
    snapshot_id: str,
    query: str,
    limit: int = 10,
    mode: str = "keyword",
    embedder=None,
    model_dir: Path = DEFAULT_MODEL_DIR,
    reranker=None,
    reranker_dir=None,
) -> list:
    if mode not in {"keyword", "vector", "hybrid", "hybrid-rerank"}:
        raise ValueError("Search mode must be keyword, vector, hybrid, or hybrid-rerank")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Query must contain between 1 and 2000 characters")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Result limit must be an integer between 1 and 50")
    try:
        snapshot = UUID(str(snapshot_id))
    except ValueError as error:
        raise ValueError("Snapshot must be a UUID") from error
    state = connection.execute(
        "SELECT state, capability, profile FROM rag_snapshots WHERE id=%s", (snapshot,)
    ).fetchone()
    if state is None:
        raise ValueError("Unknown snapshot")
    if state["state"] != "ready":
        raise ValueError("Snapshot is not ready for search")
    if mode == "keyword":
        return _keyword(connection, snapshot, query.strip(), limit)
    if state["capability"] != "vector_ready":
        raise ValueError("Snapshot is not vector-ready")
    if embedder is None:
        embedder = load_embeddings(model_dir)
    if state["profile"].get("embedding") != embedder.profile:
        raise ValueError("Snapshot embedding profile differs from the loaded model")
    # encode checks the complete tokenizer input, including special tokens.
    vector = validate_vector(embedder.encode([query.strip()])[0])
    if mode == "vector":
        return _vector(connection, snapshot, vector, limit)
    rows = fuse(
        _keyword(connection, snapshot, query.strip(), 20),
        _vector(connection, snapshot, vector, 20),
        20 if mode == "hybrid-rerank" else limit,
    )
    if mode == "hybrid-rerank":
        for rank, row in enumerate(rows, start=1):
            row["hybrid_rank"] = rank
        if reranker is None:
            from fastapi_docs_rag.rerank import DEFAULT_MODEL_DIR, load_reranker

            reranker = load_reranker(reranker_dir or DEFAULT_MODEL_DIR)
        return reranker.rerank(query.strip(), rows)[: min(limit, 20)]
    return rows
