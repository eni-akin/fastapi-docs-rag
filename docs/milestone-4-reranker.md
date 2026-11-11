# Milestone 4 reranker: operator record

Prepared: November 11, 2026. This is an implementation and smoke-test record, not a reviewed retrieval-quality result. Human label and policy review remain open in `docs/action-items.md`.

## Prepare and inspect

From the repository root, with the locked Python environment and a vector-ready snapshot:

```sh
.venv/bin/python -m fastapi_docs_rag prepare-reranker
export RAG_DATABASE_URL='host=/path/to/data/pgsocket port=55432 dbname=fastapi_docs_rag'
.venv/bin/python -m fastapi_docs_rag search --snapshot SNAPSHOT_UUID --mode hybrid-rerank --query 'How do I use a dependency with yield to close a database session?' --limit 20 --json
```

The default model directory is ignored `data/models/ms-marco-MiniLM-L6-v2`. `prepare-reranker --model-dir PATH` and `search --reranker-dir PATH` accept an explicit location. Vector embedding assets are still required for hybrid candidate generation. The model is loaded only for this search mode. `--limit` remains 1–50 for the shared search interface, while this mode returns at most 20 reranked hybrid candidates.

The response keeps the original `score` as the RRF score, keyword/vector ranks and scores, source text and `source_spans`; `hybrid_rank` records the original fused order. `rerank_score` is a raw cross-encoder logit; negative values are valid and it is not an answerability probability. `rerank_scored_text` and `rerank_source_spans` show the exact prefix scored if a pair exceeded the model limit. The original text and spans remain available for context selection. `rerank_truncated`, original/scored character counts and `rerank_pair_tokens` make the adjustment inspectable. Ties use chunk ID order.

## Pinned model and bounds

The model is [`cross-encoder/ms-marco-MiniLM-L6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) at revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, under Apache-2.0. The consumed file hashes are in `src/fastapi_docs_rag/assets/reranker/provenance.json`; only those six files are downloaded. Local loading checks all hashes, uses CPU float32, disables remote code and uses identity activation. The loaded tokenizer, model and position embeddings agree on a 512-token complete-pair limit. Questions that cannot fit are rejected before scoring; passages are shortened to traceable prefixes and complete code lines where possible. Scoring uses batches of 16.

## Real model check

On the existing 14-document, 637-chunk vector snapshot `279777ae-c949-4cae-8403-2224b314903f`, the query above produced 20 candidates. The snapshot manifest hash was `23e46b6d7b15e079b2b2bb0605e4ab23d067365a40bad9a036851b500f1861a9`, corpus fingerprint `7640cfa64e70b58458f622e46671e8965edb729113b78149f3b6050efb2bb506`, and stored profile hash `983b1abf73f3dfd87b9c9902d2acf1a24c92c84683c56208406a47ba9be57487` using the project's canonical `json_hash`. No evaluation dataset was used in this smoke check. Its top three raw logits were 4.8032, 4.6663 and 3.5693; their complete pair sizes were 52, 134 and 79 tokens. None of those 20 passages needed shortening. For all 20, the scored text was reconstructed exactly from the stored parsed document and the scored spans; the tokenizer counts matched the reported counts and stayed at or below 512. These numbers describe one inspection query, not ranking quality.

A separate 9,600-character Unicode code fixture was shortened to a 1,450-character prefix ending at a code-line boundary. Its complete pair used 508 tokens. The actual CrossEncoder preprocessing IDs matched the explicit untruncated tokenizer IDs. The model returned a finite score on the real snapshot. The full real-PostgreSQL suite passed: 158 tests.

The operator check used Python 3.12.16 with locked Sentence Transformers 5.7, Transformers 5.22 and Torch 2.15 on an ARM64 Mac. Run `RAG_TEST_DATABASE_URL='host=/path/to/data/pgsocket port=55432 dbname=postgres' PYTHONPATH=src .venv/bin/pytest -q` to repeat the suite.

The parent independently reran the 158-test suite and real model scoring. All
20 scored passages reconstructed from their saved source spans; a separate long
Unicode code fixture was explicitly shortened to a 509-token complete pair,
with preprocessing IDs matching the untruncated tokenizer IDs. Structured
evidence is in `reports/milestone-4-reranker.json`.
