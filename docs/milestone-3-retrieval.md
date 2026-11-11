# Milestone 3 retrieval commands

Run these commands from the project root after applying the vector migration and
preparing the pinned MiniLM model locally:

```sh
.venv/bin/python -m fastapi_docs_rag migrate
.venv/bin/python -m fastapi_docs_rag prepare-embeddings
.venv/bin/python -m fastapi_docs_rag embed-snapshot --snapshot KEYWORD_SNAPSHOT_UUID
.venv/bin/python -m fastapi_docs_rag search --snapshot VECTOR_SNAPSHOT_UUID --mode vector --query "dependency with yield" --json
.venv/bin/python -m fastapi_docs_rag search --snapshot VECTOR_SNAPSHOT_UUID --mode hybrid --query "Depends" --json
```

`search` defaults to `keyword` and retains its existing output. Vector search
uses the locally verified model at `data/models/all-MiniLM-L6-v2`; use
`--model-dir` to select another prepared copy of the same pinned artifacts.
Search never downloads weights. The supplied snapshot must be ready and its
stored embedding profile must exactly match the loaded model.

Vector results contain cosine `distance` and `similarity = 1 - distance`; the
score is similarity in vector mode. Similarity does not estimate whether the
passage can answer the question. Hybrid mode combines the top 20 keyword and
top 20 vector candidates using `1 / (60 + rank)` per mode. It records each
source rank and raw score, with missing ranks and scores as `null`. A requested
limit above 40 still returns at most the 40-candidate union.

Keyword queries may contain up to 2000 characters. Vector and hybrid queries
also must fit the model's 256-token input limit, including special tokens. All
modes accept limits from 1 through 50. A valid keyword query with no matches
returns an empty list; hybrid can still return vector matches.

To reuse unchanged bytes from a prior capture while adding approved pages:

```sh
.venv/bin/python -m fastapi_docs_rag capture --manifest corpus/manifests/tutorial-expanded-v2.json --output data --retained-report data/captures/SEED/report.json --retained-artifacts data
```

The capture report remains the source of provenance for imported pages. These
commands inspect retrieval only; they do not produce reviewed relevance or
answer-quality measurements.

## Seed smoke run

The [six-query seed smoke record](../reports/milestone-3-retrieval-seed-smoke.json)
contains the top five results from each mode on vector snapshot
`47dcc829-9d9c-4d8a-b492-de95683ea73c`. Four queries use exact identifiers
(`Depends`, `response_model`, `HTTPException`, `yield`); two are paraphrases.
Both paraphrases had zero keyword matches at depth five and five vector and
hybrid candidates. This is a structural observation only: the candidates have
not received human relevance labels, and the recorded short-run timings are
not a latency benchmark. The snapshot and pinned model are local artifacts;
rebuilding the same capture and vector profile yields the reproducible search
inputs without relying on this temporary database ID.
