# Milestone 1: trustworthy captured pages

Milestone 1 implements capture and extraction. The initial planning commit is
already on `main`; these implementation changes build on it. PostgreSQL,
embedding, search, and generation are subsequent work. The package setup here
provides the prerequisites needed by capture without claiming milestone 0's
database/API deliverables are complete.

## Run it

From the repository root, install the locked Python 3.12 environment:

```sh
uv sync --locked
uv run --locked python -m fastapi_docs_rag capture
```

The default manifest is `corpus/manifests/tutorial-seed.json`. An operator can
select another reviewed local manifest or artifact directory:

```sh
uv run --locked python -m fastapi_docs_rag capture \
  --manifest corpus/manifests/tutorial-seed.json \
  --output data
```

The command returns 0 only when every required page succeeds. It returns 1 for
page failures, invalid input, or an artifact/report write failure. Interrupted
work returns 130, and a report still marked `running` is incomplete.

## What gets saved

```text
data/
  raw/<raw-sha256>.html
  parsed/<content-sha256>.json
  parsed/<content-sha256>.md
  captures/<capture-uuid>/report.json
```

All artifact paths inside a report are relative to the selected output directory.
The report records the normalized manifest/hash, capture interval, parser version,
URLs, response metadata, checksums, counts, output paths, and page-level errors.
Progress is saved atomically after each page. One failed page makes the complete
capture fail, while retaining successful artifacts and failed-page raw HTML when
available for diagnosis. `data/` is ignored by Git.

Raw hashes identify uncompressed HTTP entity bytes. Requests require identity
encoding; unexpected compression is rejected before body iteration. Captures are
sequential, with a 250 ms pause between pages, a 20-second attempt deadline,
a 90-second page deadline, a 5 MiB body limit, at most three attempts, and at most
three validated redirects. Retry-After is respected only within the page deadline.

The importer accepts canonical HTTPS URLs under the official English `/tutorial/`
path. It rejects credentials, alternate hosts/ports, query strings, encoded paths,
dot segments, translations, and off-boundary redirects before requesting them.
It reads the manifest and does not follow navigation links.

The parser extracts the actual main article into ordered heading, paragraph,
list, table, quote, callout, and code blocks. Blocks retain heading paths, section
anchors, code language where available, tab-group identities/labels, and callout
metadata. Code strings retain their whitespace. Heading scopes are isolated
between tab variants. Markdown is an inspection view; JSON is the structured
source for the next milestone.

Missing article structure, missing code blocks, unknown tab layouts, an unexpected
title, or a missing reviewed code/section expectation fails the page. No partial
capture is published as a usable database snapshot; database publication is not
implemented at this milestone.

## Checked seed corpus

The seed was checked against the official navigation and captured HTML on
November 5, 2026. Each entry includes an expected title, code marker, and section
anchor to catch important layout/content regressions.

| Page | Reviewed code marker | Required section | Captured code blocks |
|---|---|---|---:|
| Request Body | `BaseModel` | `import-pydantics-basemodel` | 8 |
| Dependencies | `Depends` | `share-annotated-dependencies` | 10 |
| Dependencies with yield | `yield` | `a-database-dependency-with-yield` | 20 |
| First Steps | `FastAPI` | `check-it` | 21 |
| Path Parameters | `item_id` | `path-parameters-with-types` | 15 |
| Query Parameters | `skip` | `optional-parameters` | 19 |
| Response Model - Return Type | `response_model` | `response-model-parameter` | 21 |
| Testing | `TestClient` | `using-testclient` | 13 |

The first complete command run succeeded for all eight pages, with zero failures:
127 code blocks, 919 ordered blocks, and 1,206,846 HTML bytes. Its complete report
is retained in `reports/milestone-1-capture.json`. The corresponding raw and parsed
artifacts remain in local `data/` at the paths listed in that report.

An offline audit reparsed all eight saved raw pages and compared the resulting
documents with their JSON exports. It also compared every extracted code string
with its original `<pre>` content, checked anchor membership in the original
article, and validated all manifest expectations. All matched.

This is a captured interval of live documentation, not a pinned upstream FastAPI
release. Re-fetching later can legitimately produce different hashes; use the
retained raw bytes to reproduce this exact extraction. The report alone does not
contain the complete source corpus.

## Verification and review

```sh
uv run --locked python -m pytest -q
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
```

Tests cover URL boundaries, malformed manifests, streamed size limits, compressed
response rejection before consumption, redirects, retries, deadlines, corrupt raw
artifacts, synthetic and real HTML fixtures, exact code whitespace, long code,
tab-local headings, ordered/nested lists, tables/callouts, content hashes,
capture reports, mixed failures, export errors, and CLI success/failure behavior.
No test requires network access.

The requested subagent passes reviewed the source manifest/setup, fetch/storage,
parser/fixtures, and exports/reports. Review findings led to bounded compression
handling, isolated tab headings, and preserved loose-list numbering. Those fixes
were re-reviewed and regression-tested. The final delivery documentation, report,
all eight raw-to-parsed replays, and every saved code block passed the final
subagent audit. All 57 tests, Ruff lint, and formatting checks passed.

To continue, milestone 2 introduces token-bounded chunks, database snapshots, and
inspectable keyword search over these captured blocks.
