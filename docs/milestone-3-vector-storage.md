# Milestone 3 vector storage

`db.build_vector_snapshot(connection, source_snapshot_id, embedder)` publishes a
`vector_ready` snapshot from an explicit `ready` `keyword_only` source. The
embedder supplies a complete JSON profile and `encode(texts)`; the CLI will pass
the verified local MiniLM encoder. The result includes the new snapshot ID,
document and chunk counts, unique inputs encoded, unique inputs reused, and an
identical-build reuse flag.

Run `migrate` before building. Migration `0002_vectors.sql` enables pgvector and
adds nullable `vector(384)` embeddings. Migration `0001_keyword.sql` and the old
keyword fingerprint remain unchanged. Existing ready keyword snapshots therefore
remain usable and their chunks retain null embeddings.

The builder checks source counts, input hashes and token bounds, deduplicates
identical inputs, and reuses vectors only from ready snapshots with an exactly
equal embedding profile and input hash. It encodes misses in batches of 32 before
the final write transaction. The import advisory lock protects the fingerprint
recheck and atomic candidate publication. A failed write rolls back the entire
candidate; it does not change the selected keyword source.

The database rejects direct `ready` inserts, incomplete document or chunk counts,
missing or incompatible embedding profiles, missing embeddings, and vectors whose
norm differs from one by more than `1e-4`. Pgvector rejects nonfinite components.
Ready snapshot and content immutability triggers continue to apply to both
capabilities.

Storage verification:

```sh
PYTHONPATH=src RAG_TEST_DATABASE_URL='host=/path/to/project/data/pgsocket port=55432 dbname=postgres' \
  .venv/bin/python -m pytest tests/test_db.py tests/test_vector_db.py -q
```

The fixture creates and drops disposable databases; it does not modify the
operator's project database. Change the socket path and port for another local
PostgreSQL 17 server with pgvector 0.8.7 installed.

On the development Mac, pgvector was built from upstream tag `v0.8.7`, commit
`f37c13f68b57d2c3472b2214fbcff699d6d34876`, using
`make PG_CONFIG=/opt/homebrew/opt/postgresql@17/bin/pg_config`, followed by the
same command with `install`. Target the running PostgreSQL major version;
extension files installed for another major version are insufficient.

The parent independently ran the complete 131-test suite with real PostgreSQL,
then built the seed vector snapshot using the pinned local model: 355 chunks,
346 unique inputs encoded in 2.609 seconds. A second identical build returned the
same snapshot with zero encoding. See `reports/milestone-3-storage.json` for the
snapshot IDs and environment. This measures ingestion, not retrieval quality.
