# Milestone 4: reranking and evidence budgets

Status: ready-for-agent
Resolution: done — implementation independently verified; human semantic review deferred

## Scope

Implement [the detailed milestone-4 plan](../../docs/milestone-4-implementation-plan.md)
through three separately reviewed agent branches: pinned reranker, bounded
source-aware context, and four-mode evaluation/sufficiency diagnostics.

## Dependencies and owner decisions

- Milestone-3 agent implementation is merged, with 153 passing real PostgreSQL
  tests and independent reproduction of the 60-question diagnostic report.
- Keep the 14-page corpus, embeddings, chunking and 60-record development set
  fixed during this comparison.
- The owner explicitly deferred human label/policy reviews as action items.
  Draft diagnostics may proceed; do not invent approval or close semantic gates.
- Parent verifies each task, commits/pushes its agent-owned branch, creates and
  attaches its PR, and merges to main before dependent integration.
- Delegated implementation model approved by the owner: GPT-6 Sol, medium.

## Acceptance criteria

- Local pinned cross-encoder scores only explicitly bounded complete pairs;
  passage shortening remains traceable and questions are never silently cut.
- Evidence bundles retain exact source spans, constituent chunk IDs, compatible
  variants, source URLs, document hashes and final E1–E5 identity mappings.
- Final pinned-tokenizer chat messages fit 3,072 input tokens, reserving 768
  output tokens and a 256-token margin inside a 4,096-token total budget.
- Adjacent compatible spans can merge; full original code expansion occurs only
  when it fits and is explicitly recorded. Partial code remains labeled.
- Four retrieval modes use one frozen snapshot/dataset; selected-context coverage
  is reported separately from top-10 ranking metrics.
- Threshold sweeps report unsupported acceptance and answerable rejection with
  sample counts. Proposed policy remains unvalidated while reviews are pending.
- Real model/tokenizer checks, meaningful fixtures and the full PostgreSQL suite
  pass; exact rerun commands and per-question limitations are delivered.

## Comments

November 11, 2026: continue autonomously through implementation and per-task
merges, preserving deferred human reviews in `docs/action-items.md`. No answer
generation or serving-release activation is included in this milestone.

November 11, 2026: reranker and context branches merged. Evaluation branch produced
the four-mode 60-draft report, selected-context coverage, and unvalidated cutoff
sweep. Parent verification passed 182 tests with real PostgreSQL and tokenizer
assets; an independent four-mode run reproduced all saved aggregates and the
proposal, and checked every source span, prompt bound and cutoff denominator.
See `docs/milestone-4-handoff.md`; the integration PR records final merge state.
