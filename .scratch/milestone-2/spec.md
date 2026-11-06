# Milestone 2: captured documentation to keyword search

Status: planned; implementation and human review tracked separately below.
Base: `main` at `79d3a1a` (completed milestone 1).

## Outcome

Import the successful eight-page capture into an immutable PostgreSQL
`keyword_only` snapshot. Inspect ranked passages, exact source spans, code-fragment
labels, source URLs, and snapshot identities from an operator CLI. Preserve the
existing capture command. This expands milestone 2 and sections 5–7 of
`docs/rag-implementation-plan.md`.

## Ownership: work I can complete

| Section | Agent-owned tasks | Evidence required before commit/push |
|---|---|---|
| Chunking | Pin the MiniLM tokenizer without loading model weights; group compatible blocks; split oversized text/code without losing characters; preserve spans and variant metadata | Offline tests for token limits, exact span coverage, long code/lines/headings, Unicode, determinism, overlap, and variant boundaries; full captured-corpus audit |
| Storage | Versioned SQL migrations; snapshot/document/chunk tables; checksum-verified capture import; duplicate-import reuse; transactional publication; keyword search vectors | Real PostgreSQL tests for migration repeatability, idempotency, failed-import isolation, constraints, snapshot separation, and persisted provenance |
| Search | `search --mode keyword --snapshot ...`; weighted PostgreSQL full-text search; stable ranking; question/count bounds; readable and JSON output | Real SQL tests plus `Depends`, `response_model`, `HTTPException`, `yield`, unsupported modes, unknown snapshots, empty and overlong queries |
| Evaluation preparation | Draft 20 development questions and supporting spans from this capture; validate label references; run identifier smoke searches and export failure categories | Draft status stays explicit; every proposed span resolves; review checklist; reproducible diagnostic report without claims of human-validated quality |
| Delivery | Operator instructions and tests; section reviews; fix review findings; commits and remote branch verification | Subagent review for each section; local checks; matching GitHub branch heads |

## Ownership: input needed from you

| Input | Why a human decision matters | What can proceed before the answer |
|---|---|---|
| Preferred local PostgreSQL setup | Docker and PostgreSQL were absent when inspected; installing a native runtime changes your development machine | Chunking, SQL, mocked boundary checks, CI configuration, and evaluation drafts |
| Review the 20 proposed development questions, answerability, and evidence labels (or supply your own) | These are the ground truth used to judge retrieval; model-written labels cannot establish human-reviewed quality | Prepare explicitly unreviewed drafts, source-span validation, and diagnostic runs |
| Optional priority feedback | You may prefer security, dependencies, testing, or request/response topics | Default to balanced coverage of the existing eight-page corpus |

Confirmed in this chat: install native PostgreSQL through Homebrew and draft the
20 questions for your review. Use an isolated test/development cluster rather than
an automatically started system service. Human labels remain pending until explicitly reviewed. We will not manufacture approval
or call draft-question metrics a validated benchmark. Existing architecture and
the approved corpus boundary do not need to be reconfirmed.

## Branch and review sequence

Use stacked branches in this order, each based on the preceding reviewed branch:

1. `milestone-2/plan`
2. `milestone-2/chunking`
3. `milestone-2/storage`
4. `milestone-2/keyword-search`
5. `milestone-2/evaluation`

Commit and push each section after its tests and subagent review pass. Fix
findings on the section branch before proceeding. Later branches intentionally
contain earlier prerequisites. Keep `main` unchanged; merging is a separate
integration step. Record final branch heads and review outcomes in delivery notes.

## Implementation contracts

### Chunk artifacts

- Use the pinned `all-MiniLM-L6-v2` tokenizer, with truncation/padding disabled.
  The complete embedding input includes special tokens and stays within 256
  tokens. Start with about 180 body tokens and up to 30 overlap tokens.
- Store the exact complete heading path even when its embedding-prefix rendering
  must be shortened. Preserve original code whitespace and all source characters.
- Group only compatible section, variant, and callout blocks. Short code may
  share a passage with nearby explanation; oversized code retains block/character
  spans, a partial-code flag, and access to the full original block.
  Split oversized code at line boundaries first; use tokenizer boundaries only
  when a single line exceeds the available token budget.
- Every non-heading block is represented by source spans. Heading blocks are
  explicitly excluded as standalone bodies because they are retained as metadata.
  Whitespace between tokenizer offsets must remain covered by the source spans.
- Deterministic chunk keys cover document content, chunker/tokenizer profile,
  variants, and ordered block/character spans. Storage adds snapshot identity.

### Snapshot import and database

- Inputs: a successful milestone-1 capture report and its artifact root. Validate
  manifest/report integrity, raw hashes, parsed hashes, URLs, and expected content
  before considering the import complete. Reject incomplete, changed, or unsafe
  artifact references.
- Scope the schema to snapshots, documents, and keyword chunks. Vector values
  are absent in keyword-only snapshots; embedding generation and pgvector column
  migration belong to milestone 3.
- Use parameterized Psycopg 3 queries, numbered transactional migrations with
  migration checksums and an advisory lock, foreign keys, uniqueness, checked
  states, source spans, and full parsed document retention.
- A corpus fingerprint includes the capture manifest/content hashes and complete
  processing profile; timestamps do not affect identity. Importing an identical
  ready corpus/profile returns the prior snapshot.
- Publish all rows atomically as ready. A failed attempt must not expose partial
  searchable content or damage earlier ready snapshots. The early corpus fits one
  transaction; distributed workers and active-release pointers remain later work.
- Use a singleton local schema for this app. Tests use a dedicated temporary
  database/schema and never erase an arbitrary configured database.

### Search

- Every request names a ready snapshot explicitly; no implicit latest snapshot.
- Use weighted `simple` configuration full-text vectors, `websearch_to_tsquery`,
  `ts_rank_cd`, and a GIN index. Report it as PostgreSQL full-text ranking, not BM25.
- Return chunk/document/snapshot IDs, score, text, source URL/anchor, variants,
  source spans, token counts, and partial-code flags. Resolve ties deterministically.
- Empty, oversized, unknown-snapshot, and unsupported-mode inputs fail clearly.
  A valid query with no matches succeeds with an empty result list.

## Completion and reporting

The agent-owned implementation is complete only when code, real database behavior,
captured-corpus checks, section reviews, and remote pushes are verified. The whole
milestone also needs 20 human-reviewed questions and evidence labels. Report those
two states separately if human review remains outstanding.

No paid services, public deployment, generation model, API expansion, arbitrary
ingestion, inference-gateway integration, vector generation, or automatic merging
is part of this milestone.
