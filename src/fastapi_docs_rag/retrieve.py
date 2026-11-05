"""Inspectable PostgreSQL keyword retrieval from one explicit ready snapshot."""

from urllib.parse import quote
from uuid import UUID


def search(
    connection, snapshot_id: str, query: str, limit: int = 10, mode: str = "keyword"
) -> list:
    if mode != "keyword":
        raise ValueError("Only keyword retrieval is available at this milestone")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Query must contain between 1 and 2000 characters")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Result limit must be an integer between 1 and 50")
    try:
        snapshot = UUID(str(snapshot_id))
    except ValueError as error:
        raise ValueError("Snapshot must be a UUID") from error
    state = connection.execute(
        "SELECT state FROM rag_snapshots WHERE id=%s", (snapshot,)
    ).fetchone()
    if state is None:
        raise ValueError("Unknown snapshot")
    if state["state"] != "ready":
        raise ValueError("Snapshot is not ready for search")
    rows = connection.execute(
        """
        WITH question AS (SELECT websearch_to_tsquery('simple', %s) AS query)
        SELECT c.id::text AS chunk_id, c.snapshot_id::text AS snapshot_id,
               d.id::text AS document_id, d.source_url, d.title,
               d.content_hash AS document_content_hash,
               c.evidence_key, c.text, c.heading_path, c.section_anchor, c.variants,
               c.callout, c.source_spans, c.partial_code, c.body_tokens, c.input_tokens,
               ts_rank_cd(c.search_vector, question.query) AS score
        FROM rag_chunks c
        JOIN rag_documents d ON d.id=c.document_id AND d.snapshot_id=c.snapshot_id
        CROSS JOIN question
        WHERE c.snapshot_id=%s AND c.search_vector @@ question.query
        ORDER BY score DESC, c.id ASC
        LIMIT %s
    """,
        (query.strip(), snapshot, limit),
    ).fetchall()
    for row in rows:
        anchor = row["section_anchor"]
        row["url"] = row["source_url"] + ("#" + quote(anchor, safe="-_") if anchor else "")
    return rows
