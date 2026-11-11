# Milestone 3: vector search and hybrid comparison

Prepared: November 11, 2026.
Status update (November 11, 2026): agent-owned milestone-3 implementation and
draft three-mode diagnostics are complete. All 60 labels remain agent drafts;
the owner deferred human review and answer-sufficiency policy. The semantic
quality gate and approved benchmark remain open. See
[the handoff](milestone-3-handoff.md) and [action items](action-items.md).
Parent scope: [RAG implementation plan](rag-implementation-plan.md), milestone 3.

## Outcome

Search the same captured FastAPI documentation in three ways: PostgreSQL keyword
search, semantic vector search, and a combination of both. Produce an inspectable
CLI and a reproducible comparison on 60 human-reviewed development questions.

The question for this milestone is: **which search mode finds the evidence we
need, and where does each mode fail?** Answer generation comes later.

## Starting point and remaining milestones

`main` contains the five merged milestone-2 PRs, through `793ea16`. The retained
eight-page capture produces 355 source-traceable chunks. Keyword import/search,
checked SQL migrations, immutable snapshots, and draft-label validation exist.
The last recorded verification passed 113 tests with real PostgreSQL plus Ruff.
Those checks have not been rerun for this planning-only change.
The existing `.venv/bin/python` could not be executed during this planning session;
restore the locked environment before using the historical test result as a baseline.

The 20 existing development questions are still drafts. Merging their code did
not approve the labels or complete milestone 2's human-review gate.

| Milestone | State / remaining outcome |
|---|---|
| 0 — Reproducible skeleton | Partial: Python/package, Git, database and migrations exist; configuration example, liveness route, Compose/pgvector reproduction, and CI remain |
| 1 — Captured pages | Implementation and capture verification complete |
| 2 — Keyword search | Implementation merged; 20 question/evidence reviews pending |
| 3 — Vector and hybrid search | Next: embeddings, vector snapshots, three-mode comparison |
| 4 — Reranking and evidence budgets | Rerank candidates and build traceable, bounded context |
| 5 — Cited generation CLI | Local answer model, validated citations, initial release |
| 6 — API and full quality evaluation | Question API, final 120/80 development/test split and reviewed evaluation |
| 7 — Jobs, publication, caching, rollback | Durable updates and safe serving configuration changes |
| 8 — Usability and operating envelope | Browser UI, observability, load and recovery measurements |
| 9 — Reproduction and portfolio delivery | Fresh-environment reproduction, documentation and demonstration |

There are **seven upcoming numbered milestones, 3–9**, out of ten numbered
milestones, 0–9. Carryover from milestones 0 and 2 remains additional work; it is
not counted as another milestone or silently marked complete.

The original estimates for milestones 3–9 sum to 84–120 focused hours. Milestone
3's original allowance is 10–14 hours, to be revisited after environment checks;
model/dependency installation, parser discoveries, and human labeling can extend
it. These are planning allowances, not measured completion times or deadlines.

## Scope and working choices

- Reuse the existing chunker, exact `embedding_input`, source spans, database
  connection/migration functions, CLI, capture validation, and evaluation module.
- Keep the existing chunk size, overlap, and keyword configuration fixed during
  the three-mode comparison. Otherwise we cannot attribute changes to retrieval.
- Use `sentence-transformers/all-MiniLM-L6-v2` at the already-pinned revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Its model card specifies 384
  dimensions and default truncation beyond 256 word pieces. We must reject
  oversized inputs before encoding, including special tokens. [Model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/blob/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/README.md)
- Start with CPU float32, normalized vectors, and batches of 32. Measure memory,
  throughput and latency before considering hardware acceleration or tuning.
- Use the Sentence Transformers loader/encoder rather than hand-writing model
  pooling. Resolve compatible dependencies under Python 3.12 and commit `uv.lock`.
  Explicitly pin revision, local-only inference and normalization; these are
  supported by the official API. [Encoder documentation](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
- Use exact cosine search in PostgreSQL/pgvector and the existing snapshot index.
  Start with no approximate index. Cosine distance uses `<=>`; ascending distance
  finds nearest passages. [pgvector documentation](https://github.com/pgvector/pgvector)
- Fuse 20 keyword and 20 vector candidates using reciprocal rank fusion (RRF),
  constant 60. Final comparison depth is 10. Preserve source ranks for inspection.

No reranker, answer model, HTTP API, UI, worker, active release, answer cache, or
separate vector database is added here. Milestone-0 carryover keeps its own status;
only prerequisites needed for vector work are brought into this milestone.

## 1. Establish a runnable embedding and database environment

1. Verify local `main`, retained artifacts, PostgreSQL version, available RAM and
   disk, and the actual status of the private database cluster. Preserve existing
   data and the user's untracked `docs/project-tour.md`. Restore the managed
   Python 3.12 environment with `uv sync --locked` and rerun the baseline checks.
2. Check that pgvector can be installed for the **running PostgreSQL 17** server.
   Do not assume a package installed for another major version is compatible. If
   building from source, pin its release and target
   `/opt/homebrew/opt/postgresql@17/bin/pg_config`. Record extension/server versions.
   [Upstream installation guidance](https://github.com/pgvector/pgvector#postgres-location)
3. Resolve Sentence Transformers and its required runtime dependencies. Keep
   model imports lazy so keyword search and CLI help do not load model weights.
4. Download the pinned model to ignored `data/models/`; record consumed artifact
   hashes, model/tokenizer revision, pooling, normalization, dtype, dimension,
   tokenizer limit and license in a small provenance manifest. Keep weights out
   of Git and disable remote code execution.
5. Compare the loaded model's token IDs/counts against our packaged tokenizer,
   including 128–256-token inputs, Unicode, code and special tokens. Detect the
   saved tokenizer's 128-token truncation/padding settings and verify actual
   model inputs are complete. Set the intended 256-token ceiling explicitly.
6. Provide one explicit preparation command; searches load only the verified
   local artifacts. A missing or incompatible model gives an actionable error,
   with no implicit download during search.

**Gate:** a real local encode produces finite, nonzero, normalized 384-element
vectors; tokenizer parity and boundary checks pass; pgvector is usable in a
throwaway test database; existing keyword operations still work.

## 2. Extend storage without changing existing ready snapshots

1. Add `sql/0002_vectors.sql`; never edit checksum-recorded `0001_keyword.sql`.
   Enable `vector`, permit `keyword_only` and `vector_ready` capabilities, and add
   nullable `vector(384)` chunk embeddings. Keyword-only content remains valid.
2. Store the resolved embedding profile in snapshot metadata. Fingerprints for
   vector processing include capability, source/chunk processing identity,
   weights/tokenizer hashes, pooling, normalization, dtype and dimension. Preserve
   the old keyword fingerprint contract so old imports still reuse their snapshot.
3. Build a **new** vector-ready snapshot from an explicitly selected ready
   keyword snapshot. Copy documents/chunks with IDs scoped to the new snapshot;
   preserve exact text, input hashes, code flags, variants and source locators.
4. Encode validated inputs in bounded model batches before the final database
   write transaction. For this small corpus, keep the resulting vector map in
   memory after checking its size against the environment budget; avoid adding
   a job system or disk cache. Do not hold a database write transaction open
   during model inference.
5. Reuse vectors from existing ready vector snapshots only when exact input hash
   and the complete embedding identity agree. Deduplicate identical inputs within
   the new build. A different input or model profile is a cache miss.
6. In one publication transaction, recheck identical-build reuse under the
   existing import lock, insert the candidate rows, validate counts/vectors and
   mark ready. A failed build leaves no partial searchable snapshot. Preserve
   existing ready-content guards and extend readiness validation to vector
   completeness, including attempts to insert a snapshot directly as ready.
7. Enforce 384 dimensions, finite values and normalization (initial norm tolerance
   `1e-4`); reject zero vectors. Require all chunks in a vector-ready snapshot to
   have compatible embeddings. Keyword-only snapshots have no embeddings.

**Gate:** migrating twice is safe; the original keyword snapshot is unchanged;
the seed vector snapshot has exactly the source snapshot's document/chunk count;
an identical build reuses it with zero encoding; compatible unchanged inputs can
be reused across a replacement corpus; failed publication preserves prior data.

## 3. Add vector search and reciprocal rank fusion

Extend the existing `search()` entry point and argparse command. Keep keyword as
the default mode, its 1–2000-character bound and its current text/JSON contracts.
Add fields to describe ranking rather than removing existing source metadata.

**Vector path:** validate the requested snapshot capability and model identity,
validate the complete question token length, embed once, then run a parameterized
cosine query restricted to that snapshot in SQL. Order by distance then chunk ID.
Serialize validated vectors as bound vector parameters/casts, never SQL text
interpolation. Expose distance and a clearly labeled similarity score; neither
is an answerability probability.

**Hybrid path:** obtain 20 candidates per mode from the same snapshot and fuse:

```text
RRF(chunk) = keyword_contribution + vector_contribution
contribution = 1 / (60 + rank), with ranks starting at 1
missing from a candidate list => contribution 0
```

Deduplicate by chunk ID; break fused-score ties by chunk ID. Retain keyword rank,
vector rank, underlying scores and fused score. If keyword search returns no
matches, vector candidates can still supply the hybrid results. Never fabricate
missing ranks. Keep the existing 1–50 result bound: hybrid can return at most the
40-candidate union, and document that behavior for larger requested limits.

Unknown/unready snapshots, vector mode on keyword-only content, missing weights,
incompatible profiles, blank queries and oversized token inputs fail clearly.
Keyword-only requests do not acquire a model-token bound. A valid empty keyword
result is still success. Model and SQL failures are distinct from an empty list.

**Gate:** known small vectors have hand-checkable cosine order; RRF fixtures have
hand-computed scores; ties, duplicate candidates, empty keyword results and
cross-snapshot isolation are covered. Real model smoke queries include exact
identifiers and paraphrases, with recorded results rather than assumed wins.

## 4. Expand the captured tutorial corpus in a controlled change

Do this after three-mode search works on the original eight pages. Keep a seed
comparison separate from the expanded-corpus comparison.

1. Propose a bounded addition of roughly 6–8 official English Tutorial pages,
   prioritizing query/body validation, response status, error handling, headers,
   and dependency examples. Verify actual URLs, titles, anchors and code against
   the live official pages before writing manifest entries. No arbitrary crawler
   or Advanced Guide expansion is introduced.
2. Review the concrete addition list with the owner before capture. Each manifest
   entry needs the existing expected-title/code/section checks. Keep the seed
   manifest unchanged and version the expansion separately.
3. Capture through the bounded existing fetcher. Add small attributed HTML
   fixtures only for genuinely new structures. Fix parser gaps at their shared
   source and rerun existing variant/code/source-integrity checks.
4. Audit source coverage, exact code retention, anchors, tokens and deterministic
   chunking across every selected page. Build new keyword and vector snapshots.
5. Prefer retained bytes for unchanged seed pages in an explicitly recorded
   combined capture; if recaptured bytes differ, preserve the old capture and
   review/remap affected labels. Never replace evidence hashes merely to make
   validation pass.
6. Recheck unsupported-question labels against the larger collection: previously
   absent evidence may now be present. Freeze a dataset against that exact corpus.

**Gate:** every approved page passes capture, parsing and chunking checks. Earlier
captures/snapshots remain usable; manifests and labels identify the new corpus.

## 5. Grow the evaluation set and implement a fair comparison

1. Finish review of the existing 20 questions, then draft 40 additional records
   for **60 total**, balanced provisionally across direct lookup, paraphrase,
   multi-section and unsupported cases (about 15 each). Additions may rebalance
   existing categories; final counts depend on the owner's review.
2. Keep new questions `draft` until the owner approves or corrects expected facts,
   answerability, exact spans and evidence groups. Record reviewer/date. A group
   represents one required fact; alternatives must actually support that fact.
3. Extend label validation with category and explicit relevance grades: 2 for
   direct support, 1 for useful context. Version the expanded dataset/schema;
   keep the existing version-1 diagnostic command compatible. New grades/groups
   require review even when the underlying source text has not changed.
4. Map source spans to chunks for the selected processing snapshot. Positive
   character overlap identifies candidate relevant chunks and their annotated
   grades; report unmapped spans. For evidence-group coverage, require complete
   coverage of an approved alternative span, allowing the union of retrieved
   fragments. A one-character overlap is not complete fact coverage. Review
   questionable partial-code mappings; preserve source/variant boundaries.
5. Add hand-computed fixtures for Recall@10, MRR@10, nDCG@10 (gain `2^grade - 1`,
   discount `log2(rank + 1)`), evidence-group coverage@10 and complete-coverage
   rate. Define Recall against the fixed mapped positive-chunk set. Include
   missing results, multiple groups, alternatives, split spans, ties and
   no-positive-label cases. Report denominators and mapping limitations.
6. Run keyword/vector/hybrid against the **same vector-ready snapshot**, frozen
   questions, chunking and keyword configuration. Use top 20 candidates per
   participating retriever and evaluate the final top 10. All three modes run
   without generation or reranking. Encode each question once and disclose shared
   computation when recording timings.
7. Export JSON plus a readable Markdown summary: per-question evidence/results,
   category aggregates, rank/score details, missing groups, timings, vector reuse,
   throughput, model/runtime/schema/code identities and dataset/profile hashes.
   Separate model-load time, cold execution and warmed retrieval timing. This is
   an exploratory comparison, not milestone 8's load/capacity report.
8. Exclude unsupported questions from positive-evidence metric denominators;
   report their returned candidates separately. Vector retrieval usually returns
   neighbors even for unsupported questions: an empty-list test cannot establish
   abstention, and sufficiency thresholds remain milestone 4 work.

Do not use or tune against the later held-out test set. With pending human review,
produce explicitly draft diagnostics, not an approved quality benchmark. Completion
of agent-owned code can precede label approval; completion of the milestone cannot.

**Gate:** all 60 records have reviewed provenance and labels; all three modes are
comparable on one frozen corpus; metrics pass known-answer fixtures; misses remain
visible. Hybrid need not win every category. A weak result requires explanation,
not changing the experiment until the headline looks better.

## Implementation surfaces and delivery order

| Surface | Planned change |
|---|---|
| `pyproject.toml`, `uv.lock` | Compatible locked embedding runtime; preserve Python 3.12 |
| New `embed.py` | Local model preparation/loading, profile checks, bounded encoding and vector validation |
| `chunk.py` | Reuse tokenizer/identity; change only if parity checks expose a real issue |
| `db.py`, new `sql/0002_vectors.sql` | Capability migration, new vector snapshot build, reuse and readiness checks |
| `retrieve.py`, `cli.py` | Three search modes, inspectable scores/ranks, preparation/build/evaluation commands |
| `evaluate.py`, `evals/` | Versioned labels, span mapping, three-mode metrics and reports |
| `corpus/manifests/`, parser fixtures | Approved expanded manifest and demonstrated parser coverage |
| `tests/` | Focused model-boundary, real vector SQL, reuse/failure, ranking, CLI and metric tests |
| `reports/`, `docs/` | Reproducible run records, result summary and operator instructions |

Implement in five reviewable sections, using branches with the project default
`codex/` prefix: `codex/milestone-3/embeddings`, `/storage`, `/retrieval`, `/corpus`,
and `/evaluation` (each suffix denotes the same full prefix). Prefer sequential
PRs from updated `main` so each review contains one section. Preserve the prior
request for a subagent review of each major implementation section; fix findings
and pass relevant checks before commit/push. This planning task creates no PRs.

Planned operator flow (command names will be finalized with the CLI change):

```text
prepare-embeddings -> migrate -> embed-snapshot --snapshot <keyword snapshot>
search --mode keyword|vector|hybrid --snapshot <vector snapshot> --query <question>
compare-retrieval --snapshot <vector snapshot> --dataset <reviewed dataset>
```

Keep `capture`, `import-capture`, `diagnose-keyword` and existing keyword searches
working. New commands must have useful help, nonzero failure exits and JSON output
where appropriate. No model downloads belong in ordinary search commands.

## Verification and final handoff

Run focused unit checks during each section, then the complete suite against
fresh disposable PostgreSQL databases with pgvector. Explicitly report skipped
database/model checks rather than treating them as success. Verify the real
pinned model separately from lightweight unit fixtures, including normalization,
query limits and tokenizer parity. Run Ruff lint/format and inspect built-package
resources for the new migration and provenance manifest.

The final handoff must show: unchanged old keyword behavior; a complete immutable
vector-ready snapshot; new and reused embedding counts; successful identifier and
paraphrase searches; three-mode question-level reports; known errors; exact rerun
commands; and the actual human-review count. The existing 113-test result is the
starting baseline, not a promised future test count.

I can implement the runtime, storage, search, fixtures, evaluation machinery,
draft questions and documentation. The owner supplies semantic approval of the
60 labels and reviews the concrete corpus additions. No credentials or paid model
provider are needed for the planned local baseline. Installation compatibility,
model performance and retrieval quality remain unverified until implementation.
