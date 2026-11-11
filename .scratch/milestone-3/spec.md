# Milestone 3: vector search and hybrid comparison

Status: ready-for-agent
Resolution: done — agent implementation verified; human label review deferred by owner

## Scope

The detailed scope, dependencies, implementation sequence and acceptance gates
are in [the milestone-3 plan](../../docs/milestone-3-implementation-plan.md).
It expands milestone 3 of the agreed RAG implementation plan.

Build pinned local MiniLM embeddings, immutable vector-ready snapshots with exact
input/profile reuse, snapshot-scoped cosine search, deterministic RRF, a bounded
approved Tutorial corpus expansion, and a three-mode retrieval comparison on 60
human-reviewed development questions. Preserve existing keyword behavior.

## Dependencies

- Milestone-2 code is merged into `main` through `793ea16`.
- Verify model/runtime and PostgreSQL-17 pgvector compatibility before relying on
  them. Prepare artifacts explicitly; inference uses verified local files.
- The current 20 labels remain drafts. Human review and the expanded dataset gate
  completion of the benchmark, while implementation can proceed independently.
- Confirm the concrete corpus addition list before expanded capture.

## Acceptance criteria

- Old ready snapshots remain immutable and usable; migrations are repeatable.
- Every vector-ready chunk has a compatible normalized finite 384-element vector.
- Identical processing reuses the ready snapshot without encoding; unchanged
  inputs reuse compatible vectors across new builds.
- Vector and hybrid SQL never cross the requested snapshot; ties are deterministic.
- Model input limits are enforced before encoding without silent truncation.
- The three-mode comparison fixes corpus/questions/configuration and exports
  question-level results, metric denominators and honest failure categories.
- All 60 labels are human reviewed before reporting an approved benchmark.
- Meaningful unit, real model, and real PostgreSQL checks and section reviews pass.

## Comments

November 11, 2026: agent-owned embedding, vector storage, retrieval, corpus,
and evaluation work is implemented. The 60 development labels remain drafts:
0 human approved, 60 pending. The owner deferred these reviews and the
answer-sufficiency policy to the action items in `docs/action-items.md`.
Consequently the semantic quality gate and an approved benchmark remain open.
