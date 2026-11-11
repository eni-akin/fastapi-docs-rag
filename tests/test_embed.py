import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from fastapi_docs_rag.chunk import load_tokenizer
from fastapi_docs_rag.embed import load_embeddings, validate_vector


def test_missing_and_incompatible_model_fail_locally(tmp_path):
    with pytest.raises(ValueError, match="prepare-embeddings"):
        load_embeddings(tmp_path / "missing")
    tmp_path.joinpath("model.safetensors").write_bytes(b"wrong")
    with pytest.raises(ValueError, match="prepare-embeddings"):
        load_embeddings(tmp_path)


@pytest.mark.parametrize(
    "bad", [[0.0] * 384, [float("nan")] * 384, [float("inf")] * 384, [1e308] * 384, [1.0] * 383]
)
def test_invalid_vectors_fail(bad):
    with pytest.raises(ValueError):
        validate_vector(bad)


def test_complete_token_limit_is_checked_before_model_inference(monkeypatch):
    tokenizer, _ = load_tokenizer()
    calls = []

    class FakeModel:
        def __init__(self, *_args, **kwargs):
            assert kwargs["device"] == "cpu"
            assert kwargs["local_files_only"] is True
            assert kwargs["trust_remote_code"] is False
            self.tokenizer = lambda value, **_kwargs: {"input_ids": tokenizer.encode(value).ids}

        def get_embedding_dimension(self):
            return 384

        def float(self):
            return self

        def __iter__(self):
            return iter(type(name, (), {})() for name in ("Transformer", "Pooling", "Normalize"))

        def preprocess(self, values):
            return {"input_ids": [np.array(tokenizer.encode(values[0]).ids)]}

        def encode(self, values, **kwargs):
            calls.append((values, kwargs))
            return np.tile(np.array([1.0] + [0.0] * 383, dtype="float32"), (len(values), 1))

    monkeypatch.setattr("fastapi_docs_rag.embed._verify_files", lambda *_: None)
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeModel)
    )
    embedder = load_embeddings(Path("unused"))
    assert embedder.encode([]) == []
    assert len(embedder.encode(["word " * 254])[0]) == 384
    assert calls[0][1]["batch_size"] == 32
    assert calls[0][1]["normalize_embeddings"] is True
    assert calls[0][1]["precision"] == "float32"
    with pytest.raises(ValueError, match="256"):
        embedder.encode(["short", "word " * 255])
    assert len(calls) == 1


def test_unit_vector_is_preserved():
    value = [1 / math.sqrt(384)] * 384
    assert len(validate_vector(value)) == 384


def test_prepare_cli_does_not_connect_to_database(monkeypatch, capsys):
    import json

    from fastapi_docs_rag import cli

    monkeypatch.setattr("sys.argv", ["rag", "prepare-embeddings"])
    monkeypatch.setattr("fastapi_docs_rag.db.connect_database", lambda: 1 / 0)
    monkeypatch.setattr("fastapi_docs_rag.embed.prepare_embeddings", lambda: {"model": "pinned"})
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out) == {"model": "pinned"}
