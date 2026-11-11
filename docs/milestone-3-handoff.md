# Milestone 3 implementation handoff

The agent implementation is complete. The owner deferred review of the 20
earlier and 60 expanded development labels, as well as the answer-sufficiency
policy. All 60 expanded records are `draft` with 0 human approvals. The
comparison is a draft diagnostic, not a reviewed quality benchmark or a passed
semantic gate. See [action items](action-items.md).

## Reproduce the local comparison

From the repository root, use the managed Python 3.12 environment and the
project PostgreSQL database. The `postgres` database is only the administrator
connection used by disposable test databases.

```sh
UV_PYTHON_INSTALL_DIR=/tmp/fastapi-docs-rag-python UV_CACHE_DIR=/tmp/fastapi-docs-rag-uv-cache uv sync --locked
export RAG_DATABASE_URL='host=/Users/eniola/Documents/Project/fastapi-docs-rag/data/pgsocket port=55432 dbname=fastapi_docs_rag'
.venv/bin/python -m fastapi_docs_rag prepare-embeddings
.venv/bin/python -m fastapi_docs_rag migrate
.venv/bin/python -m fastapi_docs_rag import-capture --report data/captures/58a210e6-d72f-4938-9efa-5698e1e9fd8e/report.json --artifacts data
.venv/bin/python -m fastapi_docs_rag embed-snapshot --snapshot 887f1ba9-8a87-49fc-9610-00cc3ae3928e
.venv/bin/python -m fastapi_docs_rag compare-retrieval --snapshot 279777ae-c949-4cae-8403-2224b314903f --dataset evals/development-v2-draft.json --output reports/milestone-3-retrieval-draft.json
```

The two snapshot UUIDs above identify the retained 14-page local database.
When rebuilding in a fresh database, use the UUID returned by `import-capture`
for `embed-snapshot`, and its returned UUID for `compare-retrieval`. The last
command writes JSON, a readable `.md` summary, and a `-review.md` sheet.
Use `--build-report` with a matching vector build JSON to include exact reuse
counts in the report. The current report records 266 newly encoded inputs and
346 reused inputs from the eight-page seed snapshot; a repeat build encoded
zero. These counts refer to this retained build, not every future rerun.

## What the draft run shows

The retained expanded corpus has 14 pages and 637 chunks. The dataset has 15
questions in each provisional category: direct lookup, paraphrase, multi-section,
and unsupported. Positive metrics use 45 proposed answerable questions; the
15 unsupported questions are excluded from positive-evidence denominators and
their returned neighbors are counted separately. Related questions share
families, so 60 records do not represent 60 independent topics.

On these draft labels, keyword Recall@10 was 0.030, vector Recall@10 was 0.670,
and hybrid Recall@10 was 0.670. Complete proposed fact coverage was 0.044,
0.556, and 0.556 respectively. These measurements describe this fixed corpus,
query set, and `websearch_to_tsquery('simple')` keyword behavior. They must not
be used as approved retrieval quality or answerability estimates before owner
review. The [JSON report](../reports/milestone-3-retrieval-draft.json) records
per-question source spans, ranks, scores, missing groups, profile and schema
hashes, runtime versions, and timings; the [summary](../reports/milestone-3-retrieval-draft.md)
is shorter. The [review sheet](../reports/milestone-3-retrieval-draft-review.md)
lists every proposed fact and supporting span for owner correction.
