# Milestone 2: keyword search and human review handoff

Agent-owned implementation is complete: deterministic token-bounded chunks,
immutable PostgreSQL snapshots, explicit snapshot keyword search, and source-bound
draft-question diagnostics. The remaining milestone gate is your review of the
20 proposed development questions and evidence labels.

## Ownership and review

The work/input split and acceptance criteria are in
`.scratch/milestone-2/spec.md`. You selected native PostgreSQL and asked for drafts
to review. PostgreSQL 17.11 is installed through Homebrew. The isolated project
cluster uses `data/postgres17`, a private Unix socket in `data/pgsocket`, and port
55432 with TCP disabled. No login service was enabled. Test databases are newly
created random `rag_test_*` databases, then dropped; arbitrary existing databases
are never cleared by the test fixture.

Review `docs/milestone-2-question-review.md` and the exact supporting spans in
`evals/development-draft.json`. Send approved IDs and corrections in chat. Every
record currently remains `draft`; span validity does not establish semantic
correctness. The two proposed outside-corpus questions also need your review.

## Branches

Each branch contains its earlier prerequisites. All section code received a
subagent review and passing checks before its commit and push. All five branches
were subsequently merged into `main` through PRs #1–#5, ending at `793ea16`.

| Branch | Section |
|---|---|
| `milestone-2/plan` | Ownership split, contracts, and review sequence |
| `milestone-2/chunking` | Pinned tokenizer, deterministic passages, source coverage |
| `milestone-2/storage` | SQL migrations, capture verification, atomic immutable snapshots |
| `milestone-2/keyword-search` | Parameterized ranked search and inspectable CLI output |
| `milestone-2/evaluation` | Draft labels, provenance validation, diagnostics, and this handoff |

Use `main` to work with the cumulative implementation. The section branches remain
available as historical references. Human label approval remains outstanding.

## Run on this checkout

The database and retained milestone-1 artifacts already exist on this machine.
From the repository root:

```sh
uv sync --locked
export RAG_DATABASE_URL="host='$PWD/data/pgsocket' port=55432 dbname=fastapi_docs_rag"
uv run --locked python -m fastapi_docs_rag migrate
uv run --locked python -m fastapi_docs_rag import-capture --report reports/milestone-1-capture.json --artifacts data
```

Import returns the ready `snapshot_id`; an identical corpus/processing profile
returns the existing snapshot. Set the ID from that output:

```sh
RAG_SNAPSHOT_ID="<snapshot_id returned by import-capture>"
uv run --locked python -m fastapi_docs_rag search --mode keyword --snapshot "$RAG_SNAPSHOT_ID" --query Depends
uv run --locked python -m fastapi_docs_rag search --snapshot "$RAG_SNAPSHOT_ID" --query response_model --limit 5 --json
uv run --locked python -m fastapi_docs_rag diagnose-keyword --snapshot "$RAG_SNAPSHOT_ID" --dataset evals/development-draft.json --output reports/milestone-2-development-diagnostics.json
```

A valid search with no matches returns an empty list and succeeds. Invalid input,
unknown/unready snapshots, missing configuration, and database errors return a
clear error and nonzero exit. `--json` includes source spans, document/chunk IDs,
source links, score, variant metadata, token counts, and partial-code flags.
A partial code fragment is evidence, not a standalone runnable example.

## Fresh setup or restart

On an ARM64 Mac with Homebrew, install `postgresql@17` if needed. Initialize a
cluster only when `data/postgres17` does not already exist:

```sh
brew install postgresql@17
mkdir -p data/pgsocket
chmod 700 data/pgsocket
/opt/homebrew/opt/postgresql@17/bin/initdb -D data/postgres17 --auth-local=trust --auth-host=scram-sha-256 --no-locale -E UTF8
```

Start the isolated server when stopped, then create the project database only on
its first setup. These commands do not install a login service:

```sh
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D data/postgres17 -l data/postgres17/server.log -o "-k '$PWD/data/pgsocket' -h '' -p 55432" start
/opt/homebrew/opt/postgresql@17/bin/createdb -h "$PWD/data/pgsocket" -p 55432 fastapi_docs_rag
```

An existing PostgreSQL service can instead be selected through `RAG_DATABASE_URL`.
The application uses PostgreSQL full-text search in this milestone and requires
no pgvector extension yet. Later vector work adds its own migration.

A fresh clone also needs raw captures, because `data/` is intentionally ignored:
run the milestone-1 `capture` command and import its printed report path. The
checked-in original report alone does not supply the source HTML. If live
FastAPI documentation has changed, explicitly remap/review labels against the
new corpus; do not silently rewrite evidence hashes to make validation pass.

Stop the private server when desired with:

```sh
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D data/postgres17 stop
```

## Verification and measured behavior

```sh
export RAG_TEST_DATABASE_URL="host='$PWD/data/pgsocket' port=55432 dbname=postgres"
uv run --locked python -m pytest -q
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
```

The complete suite passed 113 tests with real PostgreSQL, with no skipped database
tests. Without `RAG_TEST_DATABASE_URL`, database tests explicitly skip; that is
not equivalent to an integration verification.

The saved eight-page corpus produces 355 chunks. All non-heading characters are
covered by exact source spans; the largest complete MiniLM input is 211 tokens
against the 256-token limit. The packaged tokenizer is pinned by upstream
revision and SHA-256, with its saved truncation and padding disabled. Large code
is split by lines first, then token boundaries for oversized individual lines.
No embedding weights are loaded at this stage.

The live database contains eight documents and 355 chunks in an immutable ready
keyword-only snapshot. Re-import reused it. Real database tests exercise failed
replacement rollback, cross-snapshot foreign keys, ready-content mutation
rejection, migration checksums, and search isolation.

The four identifier probes (`Depends`, `response_model`, `HTTPException`, `yield`)
each returned passages in the requested snapshot. The full natural-language draft
set produced 17 answerable drafts with no keyword matches, one with no proposed
evidence overlap in the top 10, and two proposed outside-corpus questions with no
matches. These are diagnostic categories based on unreviewed labels, not a quality
score. PostgreSQL's `simple` keyword configuration and conjunctive query matching
are a deliberately inspectable baseline; hybrid retrieval is later work.

Reports: `reports/milestone-2-chunking.json`, `reports/milestone-2-storage.json`,
`reports/milestone-2-keyword-search.json`, and
`reports/milestone-2-development-diagnostics.json`. The last report pins the
dataset hash and records zero human-approved labels.

The implementation does not generate answers, create embeddings, run a web API,
or choose an active serving release. Those remain later milestones.
