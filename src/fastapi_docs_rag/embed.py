"""Pinned, local-only MiniLM embeddings for documentation passages and questions."""

import hashlib
import json
import math
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from fastapi_docs_rag.chunk import load_tokenizer

DEFAULT_MODEL_DIR = Path("data/models/all-MiniLM-L6-v2")


def _manifest() -> dict:
    return json.loads(
        files("fastapi_docs_rag").joinpath("assets/minilm/model-provenance.json").read_text()
    )


def _verify_files(model_dir: Path, manifest: dict) -> None:
    if not model_dir.is_dir():
        raise ValueError(f"MiniLM is missing at {model_dir}; run prepare-embeddings first")
    for name, expected in manifest["files"].items():
        path = model_dir / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                f"MiniLM artifact {path} is missing or incompatible; run prepare-embeddings"
            )


def validate_vector(vector) -> list[float]:
    """Return a PostgreSQL-ready vector after checking the model contract."""
    values = list(vector)
    if len(values) != 384 or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("MiniLM embedding must contain 384 finite values")
    norm = math.hypot(*(float(value) for value in values))
    if norm == 0 or abs(norm - 1.0) > 1e-4:
        raise ValueError("MiniLM embedding must be nonzero and unit normalized")
    return [float(value) for value in values]


class MiniLMEmbeddings:
    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR):
        manifest = _manifest()
        _verify_files(model_dir, manifest)
        from sentence_transformers import SentenceTransformer

        try:
            model = SentenceTransformer(
                str(model_dir.resolve()),
                device="cpu",
                trust_remote_code=False,
                local_files_only=True,
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise ValueError(
                f"MiniLM at {model_dir} could not load locally; run prepare-embeddings: {error}"
            ) from error
        model.float()
        model.max_seq_length = 256
        if model.get_embedding_dimension() != 384:
            raise ValueError("MiniLM embedding dimension is incompatible; run prepare-embeddings")
        if [type(module).__name__ for module in model] != ["Transformer", "Pooling", "Normalize"]:
            raise ValueError("MiniLM pooling modules are incompatible; run prepare-embeddings")
        packaged, tokenizer_identity = load_tokenizer()
        if tokenizer_identity["sha256"] != manifest["files"]["tokenizer.json"]:
            raise ValueError("Packaged and model tokenizer identities differ")
        for sample in ("word " * 200, "def yield_例子():\n    return 'évidence'\n" * 12):
            expected = packaged.encode(sample).ids
            actual = model.preprocess([sample])["input_ids"][0].tolist()
            if expected != actual or not 128 < len(expected) <= 256:
                raise ValueError("Packaged and model tokenizers disagree on complete inputs")
        self.model = model
        self.tokenizer = packaged
        self.profile = {
            "model": manifest["model"],
            "revision": manifest["revision"],
            "files": manifest["files"],
            "pooling": manifest["pooling"],
            "normalization": "l2",
            "dtype": "float32",
            "dimension": 384,
            "max_input_tokens": 256,
            "batch_size": 32,
            "license": manifest["license"],
        }

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        values = list(texts)
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Embedding inputs must be nonblank strings")
            count = len(self.tokenizer.encode(value, add_special_tokens=True).ids)
            if count > 256:
                raise ValueError(f"Embedding input has {count} tokens; MiniLM limit is 256")
        if not values:
            return []
        embeddings = self.model.encode(
            values,
            batch_size=32,
            show_progress_bar=False,
            precision="float32",
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        if embeddings.dtype.name != "float32":
            raise ValueError("MiniLM returned embeddings with an incompatible dtype")
        return [validate_vector(vector) for vector in embeddings]


def load_embeddings(model_dir: Path = DEFAULT_MODEL_DIR) -> MiniLMEmbeddings:
    return MiniLMEmbeddings(model_dir)


def prepare_embeddings(model_dir: Path = DEFAULT_MODEL_DIR) -> dict:
    """Explicitly download the pinned revision, then verify and load it."""
    from huggingface_hub import snapshot_download

    manifest = _manifest()
    try:
        snapshot_download(
            repo_id=manifest["model"],
            revision=manifest["revision"],
            local_dir=model_dir,
            allow_patterns=list(manifest["files"]),
            max_workers=4,
        )
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not prepare pinned MiniLM at {model_dir}: {error}") from error
    return load_embeddings(model_dir).profile
