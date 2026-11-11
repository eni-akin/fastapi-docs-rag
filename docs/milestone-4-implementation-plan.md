# Milestone 4: reranking and evidence budgets

Prepared: November 11, 2026.
Status: planned implementation; semantic review remains an owner action item.
Scope: milestone 4 and sections 7.3–7.4 of the agreed RAG implementation plan.

## Outcome and inherited boundaries

Produce a printable question/context bundle from the existing hybrid search.
Rerank the top 20 fused candidates, select up to five useful evidence entries,
and preserve exact source provenance within a checked final prompt budget.
Compare keyword, vector, hybrid, and reranked hybrid on the same development set.

Milestone 3 supplies immutable keyword/vector snapshots, verified MiniLM
embeddings, exact cosine search, RRF, a 14-page corpus, and 60 development drafts.
The owner explicitly deferred human label reviews. We can implement and inspect
the complete machinery, but draft comparisons and threshold proposals are not
human-validated quality results. Keep those gates and action items visible.

Do not add answer generation, an API, background jobs, a UI, active releases, or
approximate search. Do not tune chunking, keyword configuration or embeddings
during this comparison. No held-out questions are used.

## 1. Pinned local cross-encoder and explicit pair bounds

- Use `cross-encoder/ms-marco-MiniLM-L6-v2`, revision
  `233902d25c440f23af6f7d6e94d2946bac0bee0a`, resolved from the upstream model API.
  Pin consumed file hashes and license metadata; download only through an
  explicit preparation command into ignored `data/models/`.
- Load through the installed Sentence Transformers `CrossEncoder`, local files
  only, CPU float32, no remote code. Use an explicit identity activation so the
  reported score is a raw ranking logit rather than an implied probability.
- Read and verify the tokenizer/model pair limit from the actual pinned files.
  Count question plus passage plus pair special tokens without automatic
  truncation. Check the question alone first; never silently shorten it.
- Score existing chunk body text. If a pair is too long, shorten the passage
  deliberately to an exact source-text prefix that fits, retaining adjusted
  block/character spans, original/scored lengths and a truncation flag. Prefer
  line boundaries for code when possible; use tokenizer offsets as the fallback.
- Run bounded scoring batches. Reject nonfinite scores or wrong result counts.
  Preserve prior ranks/scores and all source metadata. Break score ties by chunk
  ID and never mix snapshots.

Gate: real pinned-model scoring, exact pair-boundary tests, unchanged question
text, traceable truncated passages, finite logits and deterministic ordering.
Existing keyword/vector/hybrid behavior and lazy loading must remain intact.

Sources: [model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2),
[CrossEncoder API](https://www.sbert.net/docs/package_reference/cross_encoder/model.html).

## 2. Context selection with exact spans and final prompt counting

- Prepare only the tokenizer assets for `Qwen/Qwen2.5-1.5B-Instruct`, revision
  `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, with file checksums, license and chat
  template identity. No generation weights or model server are needed here.
- Create one versioned grounded-message renderer shared by context budgeting and
  the later generator. Evidence is quoted data. Keep instructions, question,
  evidence IDs, source labels and the generation prefix inside token counting.
- Count using `apply_chat_template(..., tokenize=True,
  add_generation_prompt=True)` on the pinned local tokenizer. Avoid adding
  special tokens twice. The later llama.cpp/GGUF integration must verify parity
  with this tokenizer/template before claiming a production prompt bound.
- Start at 4,096 total tokens, reserve 768 output tokens and a 256-token margin:
  the complete input prompt may use at most 3,072 tokens. Reject a question whose
  instructions/question alone exceed the input budget.
- Select at most five evidence entries in reranked order, preferring distinct
  supporting sections. Deduplicate exact and overlapping content without
  dropping required source metadata. Do not combine incompatible code variants
  or callout contexts into a synthetic example.
- Merge adjacent/overlapping spans only when document, section, ordering and
  variant/callout metadata agree. Reconstruct text from saved source spans;
  retain every constituent chunk ID and document hash.
- When a selected partial code block can fit in full, expand from the same saved
  parsed document and record that expansion. Otherwise retain the partial-code
  warning. Never execute code or invent omitted lines.
- Fit whole entries/valid expansions using the complete rendered prompt count.
  Record skipped candidates and reasons. Assign final request-local E1–E5 IDs
  after selection, then recount the actual exported messages.

Gate: every entry resolves to source spans in one snapshot; variants remain
separate; prompt + reserved output + margin fits the total; long code, Unicode,
empty results, overlap and tight-budget cases have meaningful fixtures.

Sources: [Qwen model/tokenizer](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct),
[chat-template tokenization](https://huggingface.co/docs/transformers/main/en/chat_templating).

## 3. Four-mode diagnostics and a provisional sufficiency policy

- Extend the existing comparison rather than creating a parallel evaluator.
  Use the same 60 draft records, snapshot and retrieval profile. Rerank only the
  top 20 hybrid candidates and report top-10 retrieval metrics for all modes.
- Report selected-context evidence-group coverage separately from top-10
  ranking metrics. Up to five selected entries is a different denominator/view;
  merged/expanded entries retain constituent source spans for coverage checks.
- Export per-question scores, selected/skipped evidence, token counts, missing
  groups, source IDs and timings. Separate model load, retrieval, scoring and
  selection. Record any shared computation explicitly.
- An empty evidence list is immediately insufficient. For nonempty evidence,
  implement a versioned development threshold proposal using raw reranker
  scores; sweep observed cutoffs and record unsupported acceptance and answerable
  rejection rates with denominators. Do not represent scores as probabilities.
- Report group completeness for multi-fact questions. A high top score alone
  does not prove that the selected context can answer every required fact.
- Because all labels remain drafts, the resulting policy is explicitly
  unvalidated and cannot become an approved serving gate. The bundle exposes
  that status; quality review remains an owner action item. Later generation
  must still abstain when the supplied evidence is insufficient.

Gate: known-answer fixtures validate threshold accounting; all four modes and
selected contexts are inspectable; review counts and limitations are prominent.
A poor reranking result is recorded, not hidden by changing the frozen inputs.

## Branches, verification and delivery

Use separate agent-owned branches and parent verification/commit/PR/merge for:

1. `codex/milestone-4/reranker`: model preparation, pair bounds, scoring, search
   mode/CLI integration, tests and real model report.
2. `codex/milestone-4/context`: tokenizer-only preparation, prompt renderer,
   source-aware selection/expansion, printable/JSON context command and tests.
3. `codex/milestone-4/evaluation`: four-mode comparison, selected-context metrics,
   provisional sufficiency calibration, reports and runbook.

Reuse `retrieve.py`, `evaluate.py`, CLI argument patterns, artifact writes and
existing span/identity helpers. Add focused `rerank.py` and `context.py` modules;
avoid a provider/pipeline class hierarchy. Share artifact checksum logic only
where the actual second consumer makes it useful.

The parent reviews code and meaningful edge cases, runs the complete suite with
real PostgreSQL, and independently checks real model/tokenizer behavior before
each task is merged. Reports identify source/model/tokenizer/profile/dataset
hashes, schema/code versions, hardware and exact commands. Inspect package
resources and ensure model weights remain ignored.

The final handoff includes a real context bundle, four-mode draft diagnostics,
budget and provenance verification, a clearly unvalidated threshold proposal,
merged PR links, and remaining owner review actions. The original milestone
estimate is 8–12 focused hours; runtime/model setup and review can extend it.
