# Milestone 3 tutorial corpus expansion

The reviewed [`tutorial-expanded-v2.json`](../corpus/manifests/tutorial-expanded-v2.json)
contains the original eight seed pages, unchanged, plus six approved English
Tutorial pages: body fields, classes as dependencies, handling errors, header
parameters, query string validation, and response status code. Every entry has a
captured title, code, and section-anchor check. No new parser fixture was needed:
all six pages used structures already covered by the existing parser fixtures.

## Capture and provenance

The original eight raw and parsed artifacts come from capture
`4b6f1a40-a9f6-4738-aaaa-1f86d8f5937e` (November 5). The bounded fetcher
downloaded only the six new pages into capture
`08903fce-63b0-470d-a636-54689fd65a61` (November 11). After checking the
new pages' actual section IDs, capture
`58a210e6-d72f-4938-9efa-5698e1e9fd8e` revalidated all 14 pages against
the final manifest without network requests. Its retained-capture chain and
per-page `fetched_at` values distinguish reused bytes from newly fetched bytes.
The overall capture interval is November 5–11, not one upstream FastAPI commit.

The ignored artifacts currently live at `/private/tmp/rag-m3-corpus-data` and
must be copied into this project's ignored `data/` directory before import.
The reviewed summary is [`reports/milestone-3-corpus.json`](../reports/milestone-3-corpus.json).
The final report is `data/captures/58a210e6-d72f-4938-9efa-5698e1e9fd8e/report.json`.
Keep the old capture and its artifacts; do not overwrite its report.

To repeat the six-page fetch from a checkout with the original capture under
`data/`, run this from the repository root. The importer validates the complete
retained capture before copying its raw and parsed bytes. Its normal fetch limits
are a 20-second request timeout, 5 MiB identity-encoded body maximum (compressed
responses are rejected), three attempts,
and sequential requests.

```sh
PYTHONPATH=src .venv/bin/python - <<'PY'
import asyncio
from pathlib import Path
import httpx
from fastapi_docs_rag.fetch import FetchLimits
from fastapi_docs_rag.ingest import capture

async def main():
    limits = FetchLimits()
    async with httpx.AsyncClient(
        timeout=limits.request_timeout,
        headers={"user-agent": "fastapi-docs-rag/0.1 (documentation capture)"},
        trust_env=False,
    ) as client:
        path, report = await capture(
            Path("corpus/manifests/tutorial-expanded-v2.json"),
            Path("data"),
            client,
            limits,
            Path("data/captures/4b6f1a40-a9f6-4738-aaaa-1f86d8f5937e/report.json"),
            Path("data"),
        )
    print(path, report["status"], report["pages_succeeded"], report["pages_failed"])

asyncio.run(main())
PY
```

## Validation

`load_capture` replayed all raw HTML through parser version 1 and checked every
raw hash, parsed hash, title, required code string, section anchor, and count.
An additional audit compared every raw `<pre>` text with the ordered parsed code
blocks, checked every parsed section anchor in the raw article, covered every
character of every non-heading block by chunk source spans, and reran parsing
and chunking for deterministic equality. All 14 passed. The original eight
yielded the same 355 chunks as before; the six additions yield 282, for 637
total. The largest embedding input is 211 tokens, below the 256-token limit;
body text is at most 180 tokens. Per-page hashes and counts are in the JSON
report.

Run the integrity and regression checks after copying the artifacts:

```sh
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from fastapi_docs_rag.db import load_capture
from fastapi_docs_rag.chunk import chunk_document

root = Path("data")
report, documents = load_capture(
    root / "captures/58a210e6-d72f-4938-9efa-5698e1e9fd8e/report.json", root
)
assert len(documents) == 14
chunks = [chunk_document(document) for document in documents]
assert sum(len(result["chunks"]) for result in chunks) == 637
assert all(chunk["input_tokens"] <= 256 for result in chunks for chunk in result["chunks"])
print(report["capture_id"], len(documents), sum(len(result["chunks"]) for result in chunks))
PY
PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider
RUFF_CACHE_DIR=/tmp/rag-ruff-cache .venv/bin/python -m ruff check .
RUFF_CACHE_DIR=/tmp/rag-ruff-cache .venv/bin/python -m ruff format --check .
```

Keyword and vector snapshot builds belong to the storage/embedding integration
work. The 20 existing question labels remain drafts; the expanded corpus may
change their answerability and needs owner review before a quality benchmark.
