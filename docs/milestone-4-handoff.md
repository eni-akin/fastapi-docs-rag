# Milestone 4 implementation handoff

The agent implementation covers pinned local cross-encoder reranking, source-checked
context assembly, and a four-mode evaluation on the unchanged 14-page,
637-chunk vector snapshot. The 60-question development set remains **60 draft,
0 human approved**. The numbers below are diagnostics, not a reviewed quality
benchmark. The threshold proposal is **unvalidated and not approved for serving**.
Human label and policy review remain in [action items](action-items.md).

## Reproduce the draft comparison

Use the locked project Python 3.12 environment, prepared model files, and the
retained PostgreSQL application database. From the repository root:

```sh
export RAG_DATABASE_URL="host='$PWD/data/pgsocket' port=55432 dbname=fastapi_docs_rag"
.venv/bin/python -m fastapi_docs_rag compare-retrieval \
  --snapshot 279777ae-c949-4cae-8403-2224b314903f \
  --dataset evals/development-v2-draft.json \
  --output reports/milestone-4-retrieval-draft.json \
  --with-rerank
```

Use the returned snapshot UUID when rebuilding in a fresh database, as described
in the [milestone-3 handoff](milestone-3-handoff.md). A matching vector build JSON
can optionally be supplied with `--build-report` to record embedding reuse counts.
Without `--with-rerank`, the command
retains the earlier three-mode behavior and does not load reranker or context
tokenizer assets. The four-mode command exports [full question diagnostics](../reports/milestone-4-retrieval-draft.json),
[summary](../reports/milestone-4-retrieval-draft.md), [review sheet](../reports/milestone-4-retrieval-draft-review.md),
and [separate policy proposal](../reports/milestone-4-retrieval-draft-policy.json).
The JSON includes snapshot, corpus, dataset, profile, schema, code and model
identities; source spans/ranks/scores; selected and skipped context entries;
exact prompt tokens; missing fact groups; and stage timings. Model loading is
timed separately. Keyword/vector candidate lists and one query encode are
shared by baseline hybrid and reranked hybrid. Top-20 RRF candidates are scored
once, with top-10 retrieval metrics distinct from selected-context coverage.

## Observed draft diagnostics

| Mode | Recall@10 | Complete proposed fact coverage@10 |
|---|---:|---:|
| Keyword | 0.030 | 0.044 |
| Vector | 0.670 | 0.556 |
| Hybrid | 0.670 | 0.556 |
| Hybrid rerank | 0.689 | 0.622 |

The ranking result is mixed: overall complete proposed coverage@10 rose from
0.556 to 0.622, while paraphrase MRR@10 fell from 0.650 to 0.583. The
question-level misses in the [summary](../reports/milestone-4-retrieval-draft.md)
and full JSON remain essential to review.

The five-entry selected context covered every proposed fact group for 0.489
of the 45 proposed answerable questions. This differs from top-10 ranking
coverage: a selected entry must contain a full supporting source-span
alternative, possibly across compatible merged fragments. The maximum actual
prompt was 2,175 tokens, below the 3,072 input bound. The separate
[real context bundle](../reports/milestone-4-context.json) records one inspected
query with source IDs, exact spans and 1,170 prompt tokens. Neither result
establishes answer generation quality or GGUF/llama.cpp tokenizer parity.

**The apparent 45/15 answerability separation is not complete evidence
sufficiency.** Fewer than half of proposed answerable questions had complete
selected-context fact coverage. A raw ranking score cannot establish answer
correctness or safely serve as the only sufficiency gate.

The provisional raw-score sweep proposes cutoff `-4.891684532165527` and,
on these drafts, accepts 0/15 proposed unsupported questions and rejects
0/45 proposed answerable questions. It uses the best raw score among chunks
actually included in selected context; empty context always returns
insufficient. This apparent separation may change when labels are reviewed or
new questions arrive. The policy file retains every observed cutoff, exact
class denominators, endpoint behavior and tie rule. The proposal binds the
dataset/review counts, retrieval/reranker/context profiles, code/schema hashes
and a recomputable full-report identity. It is not a probability or an active
release policy.

## Remaining owner actions

1. Review all 60 answerability labels, facts, alternatives, spans and grades on
   the linked review sheet. Record reviewer and time on approved records.
2. Inspect context misses and unsupported cases in the full JSON. Re-run the
   comparison if labels change.
3. Review the cutoff tradeoff with approved labels and later generation traces
   before choosing any serving sufficiency rule.
4. At milestone 5, verify tokenizer/chat-template parity against the actual
   GGUF/llama.cpp stack before treating this prompt count as a production bound.

No generation, API, active release or held-out evaluation is part of this
milestone. The original chunking, keyword settings, embeddings and draft set
were held fixed.

## Verification

The parent independently ran all 182 tests with disposable PostgreSQL databases
and prepared tokenizer assets, plus Ruff lint/format checks. An offline-model
rerun of the complete four-mode CLI reproduced every saved aggregate and the
cutoff proposal. Every question's selected spans, variants, document hashes,
selected-score identity and final prompt count were checked; every cutoff's
class counts were recomputed. The policy's declared report hash was verified.
Both preparation commands were also exercised against the pinned local files.
