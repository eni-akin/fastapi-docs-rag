# Pinned local embeddings

From the repository root, restore the locked Python 3.12 environment and prepare
the model explicitly:

```sh
UV_PYTHON_INSTALL_DIR=/tmp/fastapi-docs-rag-python UV_CACHE_DIR=/tmp/fastapi-docs-rag-uv-cache uv sync --locked
.venv/bin/python -m fastapi_docs_rag prepare-embeddings
```

The command downloads revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
of `sentence-transformers/all-MiniLM-L6-v2` to ignored
`data/models/all-MiniLM-L6-v2/`. It verifies every model file used by the loader
against the committed provenance manifest. Loading for inference uses only that
local directory and fails with a `prepare-embeddings` instruction when artifacts
are missing or incompatible. Keyword search and CLI help do not import model
weights or require the local model.

`load_embeddings()` returns an object with `.profile` and `.encode(texts)`.
Encoding checks complete token counts before inference, including special
tokens, and returns 384-dimensional normalized float32 vectors as Python lists.
The runtime fixes CPU execution and batches of 32. `validate_vector()` checks
the output contract again at storage boundaries. The model identity includes
the pinned revision and SHA-256 of all consumed files; use the entire `.profile`
in vector snapshot identity and compatibility checks.

The local model run and tokenizer parity results are saved in
`reports/milestone-3-embeddings.json`. This report is an embedding smoke check,
not a retrieval quality benchmark.
