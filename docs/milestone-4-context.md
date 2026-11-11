# Milestone 4 context assembly

The context builder accepts ranked chunks from one explicit ready snapshot. It
checks each chunk and its source metadata against PostgreSQL, reconstructs text
from saved parsed-document spans, and returns at most five evidence entries.
Each final `E1`–`E5` ID maps to a document hash, section URL, exact block and
character spans, and all contributing chunk IDs. Compatible touching spans may
merge; conflicting code variants and callouts remain separate. A partial code
fragment expands only from its own saved block when the complete prompt still
fits. Otherwise `partial_code` remains true.

Run `prepare-context-tokenizer` explicitly to download only the pinned
`Qwen/Qwen2.5-1.5B-Instruct` tokenizer JSON, configuration and Apache 2.0
license into ignored `data/models/qwen2.5-1.5b-tokenizer`. The pinned revision,
three SHA-256 file checksums and chat-template checksum are in
`src/fastapi_docs_rag/assets/qwen-tokenizer/provenance.json`. Loading is
local-only and rejects changed files or templates. No generation weights are
downloaded or loaded.

`grounded-evidence-v1` renders the same two chat messages for counting and
later generation. It quotes evidence as JSON data, includes source labels and
request-local IDs, and counts the actual generation prefix with
`apply_chat_template(tokenize=True, add_generation_prompt=True)`. The complete
input limit is 3,072 tokens, reserving 768 output tokens and a 256-token margin
within 4,096 total. A question that cannot fit by itself is rejected. The
bundle records selected and skipped chunks, exact prompt token use, and the
unvalidated status of the later sufficiency policy.

`bundle.profile` binds the prompt version, source-span selection version,
SHA-256 of the fixed system/user framing, tokenizer identity, total/input/output
and margin budgets, and the five-entry limit. The companion `evidence_lookup`
maps each final ID to its content and raw document hashes, URL, spans and chunk
IDs. `bundle.messages` is the exact pair of messages counted and exported.

## Real local check

On the existing 14-page vector snapshot
`279777ae-c949-4cae-8403-2224b314903f`, the command below wrote
`reports/milestone-4-context.json`:

```sh
RAG_DATABASE_URL='host=/Users/eniola/Documents/Project/fastapi-docs-rag/data/pgsocket port=55432 dbname=fastapi_docs_rag' \
PYTHONPATH=src /Users/eniola/Documents/Project/fastapi-docs-rag/.venv/bin/python -m fastapi_docs_rag context \
  --snapshot 279777ae-c949-4cae-8403-2224b314903f \
  --query 'How do I use a dependency with yield to close a database session?' \
  --model-dir /Users/eniola/Documents/Project/fastapi-docs-rag/data/models/all-MiniLM-L6-v2 \
  --reranker-dir /Users/eniola/Documents/Project/fastapi-docs-rag/data/models/ms-marco-MiniLM-L6-v2 \
  --tokenizer-dir /Users/eniola/Documents/Project/fastapi-docs-rag/data/models/qwen2.5-1.5b-tokenizer \
  --json > reports/milestone-4-context.json
```

This yielded five entries and 15 skipped candidates. The actual exported
chat-template input was 1,170 tokens, below 3,072. An independent read of the
saved PostgreSQL parsed documents reconstructed all five entry texts from
their recorded spans and matched both document hashes; reapplying the pinned
chat template to the exported messages also returned 1,170 tokens. These
entries come from distinct sections of the dependencies-with-yield tutorial
page. This is a traceability/budget check, not a reviewed answer-quality result.

Tests run offline by default. Setting `RAG_CONTEXT_TOKENIZER_DIR` to prepared
assets enables the real tokenizer check; `RAG_TEST_DATABASE_URL` enables the
PostgreSQL fixture check. Preparation never occurs implicitly in tests.

This is a Hugging Face tokenizer/template bound. The later GGUF/llama.cpp
integration must check token and chat-template parity before treating it as a
production generation bound. The bundle contains no generated answer.
