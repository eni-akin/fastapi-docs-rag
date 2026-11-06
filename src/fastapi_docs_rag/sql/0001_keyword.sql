CREATE TABLE rag_snapshots (
    id uuid PRIMARY KEY,
    fingerprint text NOT NULL UNIQUE,
    capability text NOT NULL DEFAULT 'keyword_only' CHECK (capability = 'keyword_only'),
    state text NOT NULL CHECK (state IN ('building', 'ready')),
    manifest_hash text NOT NULL,
    profile jsonb NOT NULL,
    capture jsonb NOT NULL,
    document_count integer NOT NULL CHECK (document_count > 0),
    chunk_count integer NOT NULL CHECK (chunk_count > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_documents (
    id uuid PRIMARY KEY,
    snapshot_id uuid NOT NULL REFERENCES rag_snapshots(id),
    source_url text NOT NULL,
    title text NOT NULL,
    content_hash text NOT NULL,
    raw_hash text NOT NULL,
    document jsonb NOT NULL,
    UNIQUE (snapshot_id, source_url),
    UNIQUE (id, snapshot_id)
);

CREATE TABLE rag_chunks (
    id uuid PRIMARY KEY,
    snapshot_id uuid NOT NULL REFERENCES rag_snapshots(id),
    document_id uuid NOT NULL,
    chunk_key text NOT NULL,
    evidence_key text NOT NULL,
    text text NOT NULL CHECK (length(text) > 0),
    heading_path jsonb NOT NULL,
    section_anchor text,
    variants jsonb NOT NULL,
    callout jsonb,
    source_spans jsonb NOT NULL,
    partial_code boolean NOT NULL,
    embedding_input text NOT NULL,
    embedding_input_hash text NOT NULL,
    body_tokens integer NOT NULL CHECK (body_tokens BETWEEN 0 AND 254),
    input_tokens integer NOT NULL CHECK (input_tokens BETWEEN 2 AND 256),
    search_vector tsvector NOT NULL,
    UNIQUE (snapshot_id, chunk_key),
    FOREIGN KEY (document_id, snapshot_id) REFERENCES rag_documents(id, snapshot_id)
);

CREATE INDEX rag_chunks_snapshot ON rag_chunks(snapshot_id);
CREATE INDEX rag_chunks_search ON rag_chunks USING gin(search_vector);

CREATE FUNCTION rag_guard_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'ready' THEN
        RAISE EXCEPTION 'Ready snapshots are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
CREATE TRIGGER rag_snapshot_immutable BEFORE UPDATE OR DELETE ON rag_snapshots
FOR EACH ROW EXECUTE FUNCTION rag_guard_snapshot();

CREATE FUNCTION rag_guard_content() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    old_snapshot uuid;
    new_snapshot uuid;
BEGIN
    IF TG_OP <> 'INSERT' THEN old_snapshot := OLD.snapshot_id; END IF;
    IF TG_OP <> 'DELETE' THEN new_snapshot := NEW.snapshot_id; END IF;
    PERFORM 1 FROM rag_snapshots
    WHERE id IN (old_snapshot, new_snapshot) ORDER BY id FOR SHARE;
    IF EXISTS (
        SELECT 1 FROM rag_snapshots
        WHERE id IN (old_snapshot, new_snapshot) AND state = 'ready'
    ) THEN
        RAISE EXCEPTION 'Ready snapshot content is immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
CREATE TRIGGER rag_documents_immutable BEFORE INSERT OR UPDATE OR DELETE ON rag_documents
FOR EACH ROW EXECUTE FUNCTION rag_guard_content();
CREATE TRIGGER rag_chunks_immutable BEFORE INSERT OR UPDATE OR DELETE ON rag_chunks
FOR EACH ROW EXECUTE FUNCTION rag_guard_content();
