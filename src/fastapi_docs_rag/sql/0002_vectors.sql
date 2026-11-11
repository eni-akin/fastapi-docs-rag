CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE rag_snapshots DROP CONSTRAINT rag_snapshots_capability_check;
ALTER TABLE rag_snapshots ADD CONSTRAINT rag_snapshots_capability_check
    CHECK (capability IN ('keyword_only', 'vector_ready'));
ALTER TABLE rag_chunks ADD COLUMN embedding vector(384);

CREATE FUNCTION rag_validate_ready_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    actual_documents bigint;
    actual_chunks bigint;
    valid_vectors bigint;
BEGIN
    IF NEW.state <> 'ready' THEN
        RETURN NEW;
    END IF;
    SELECT count(*) INTO actual_documents FROM rag_documents WHERE snapshot_id = NEW.id;
    SELECT count(*) INTO actual_chunks FROM rag_chunks WHERE snapshot_id = NEW.id;
    IF actual_documents <> NEW.document_count OR actual_chunks <> NEW.chunk_count THEN
        RAISE EXCEPTION 'Ready snapshot row counts are incomplete';
    END IF;
    IF NEW.capability = 'vector_ready' THEN
        IF jsonb_typeof(NEW.profile->'embedding') IS DISTINCT FROM 'object'
            OR NEW.profile->'embedding' = '{}'::jsonb
            OR NEW.profile->'embedding'->>'normalization' IS DISTINCT FROM 'l2'
            OR NEW.profile->'embedding'->>'dtype' IS DISTINCT FROM 'float32'
            OR NEW.profile->'embedding'->>'dimension' IS DISTINCT FROM '384'
            OR NEW.profile->'embedding'->>'max_input_tokens' IS DISTINCT FROM '256'
            OR NEW.profile->'embedding'->>'batch_size' IS DISTINCT FROM '32'
            OR coalesce(NEW.profile->'embedding'->>'model', '') = ''
            OR coalesce(NEW.profile->'embedding'->>'revision', '') = ''
            OR coalesce(NEW.profile->'embedding'->>'pooling', '') = ''
            OR coalesce(NEW.profile->'embedding'->>'license', '') = ''
            OR jsonb_typeof(NEW.profile->'embedding'->'files') IS DISTINCT FROM 'object'
            OR NEW.profile->'embedding'->'files' = '{}'::jsonb THEN
            RAISE EXCEPTION 'Vector-ready snapshot requires an embedding profile';
        END IF;
        SELECT count(*) INTO valid_vectors FROM rag_chunks
        WHERE snapshot_id = NEW.id AND embedding IS NOT NULL
            AND vector_dims(embedding) = 384
            AND vector_norm(embedding) > 0
            AND abs(vector_norm(embedding) - 1) <= 0.0001;
        IF valid_vectors <> NEW.chunk_count THEN
            RAISE EXCEPTION 'Vector-ready snapshot has incomplete or invalid embeddings';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM rag_chunks WHERE snapshot_id = NEW.id AND embedding IS NOT NULL) THEN
        RAISE EXCEPTION 'Keyword-only snapshot cannot contain embeddings';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER rag_snapshot_ready_check BEFORE INSERT OR UPDATE ON rag_snapshots
FOR EACH ROW EXECUTE FUNCTION rag_validate_ready_snapshot();
