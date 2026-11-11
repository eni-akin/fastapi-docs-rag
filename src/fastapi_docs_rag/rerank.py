"""Pinned local cross-encoder scoring of complete, source-traceable pairs."""

import hashlib
import json
import math
from importlib.resources import files
from pathlib import Path

DEFAULT_MODEL_DIR = Path("data/models/ms-marco-MiniLM-L6-v2")


def _manifest():
    return json.loads(
        files("fastapi_docs_rag").joinpath("assets/reranker/provenance.json").read_text()
    )


def _verify_files(model_dir, manifest):
    if not model_dir.is_dir():
        raise ValueError(f"Reranker missing at {model_dir}; run prepare-reranker first")
    for name, expected in manifest["files"].items():
        path = model_dir / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                f"Reranker artifact {path} is missing or incompatible; run prepare-reranker"
            )


def _source_prefix(row, length):
    """Map an exact prefix of joined chunk text back to original block spans."""
    spans = []
    position = 0
    for index, span in enumerate(row["source_spans"]):
        if index:
            if length < position + 2:
                length = position
                break
            position += 2
        available = span["end"] - span["start"]
        take = min(available, max(0, length - position))
        if take:
            spans.append({**span, "end": span["start"] + take})
        position += available
        if position >= length:
            break
    represented = sum(span["end"] - span["start"] for span in spans) + 2 * (len(spans) - 1)
    return row["text"][: min(length, represented)], spans


class MiniLMReranker:
    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR):
        from sentence_transformers import CrossEncoder
        from torch.nn import Identity

        manifest = _manifest()
        _verify_files(model_dir, manifest)
        try:
            model = CrossEncoder(
                str(model_dir.resolve()),
                device="cpu",
                local_files_only=True,
                trust_remote_code=False,
                activation_fn=Identity(),
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise ValueError(f"Pinned reranker could not load locally: {error}") from error
        model.model.float()
        tokenizer = model.tokenizer
        limit = min(
            model.max_seq_length,
            tokenizer.model_max_length,
            model.model.config.max_position_embeddings,
        )
        if limit != 512 or model.model.config.num_labels != 1:
            raise ValueError("Pinned reranker pair limit or output shape is incompatible")
        for question, passage in (
            ("what is this", "text " * 300),
            ("évidence?", "def 例子():\n    pass\n" * 20),
        ):
            expected = tokenizer(question, passage, truncation=False)["input_ids"]
            actual = model.preprocess([(question, passage)])["input_ids"][0].tolist()
            if len(expected) <= limit and expected != actual:
                raise ValueError("CrossEncoder preprocessing changes a complete pair")
        self.model = model
        self.tokenizer = tokenizer
        self.limit = limit
        self.profile = {
            "model": manifest["model"],
            "revision": manifest["revision"],
            "files": manifest["files"],
            "license": manifest["license"],
            "device": "cpu",
            "dtype": "float32",
            "activation": "identity",
            "max_pair_tokens": limit,
            "batch_size": 16,
            "scored_field": "text",
        }

    def _count(self, query, passage):
        return len(self.tokenizer(query, passage, truncation=False)["input_ids"])

    def _bounded(self, query, row):
        original = row["text"]
        count = self._count(query, original)
        if count <= self.limit:
            return original, row["source_spans"], count
        offsets = self.tokenizer(
            original, add_special_tokens=False, truncation=False, return_offsets_mapping=True
        )["offset_mapping"]
        cuts = sorted({end for _, end in offsets if end > 0} | {len(original)})
        low, high = 0, len(cuts)
        while low < high:
            mid = (low + high) // 2
            if self._count(query, original[: cuts[mid]]) <= self.limit:
                low = mid + 1
            else:
                high = mid
        if low == 0:
            raise ValueError("No passage character fits the reranker pair limit")
        length = cuts[low - 1]
        if row.get("partial_code") or "\n" in original:
            line_end = original.rfind("\n", 0, length)
            if line_end > 0:
                length = line_end + 1
        scored, spans = _source_prefix(row, length)
        pair_tokens = self._count(query, scored)
        if pair_tokens > self.limit:
            for cut in reversed(cuts[: low - 1]):
                scored, spans = _source_prefix(row, cut)
                pair_tokens = self._count(query, scored)
                if scored and pair_tokens <= self.limit:
                    break
        if not scored or pair_tokens > self.limit:
            raise ValueError("Reranker prefix does not fit the pair limit")
        return scored, spans, pair_tokens

    def rerank(self, query: str, rows: list[dict]) -> list[dict]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Reranker question must be nonblank")
        if self._count(query, "") > self.limit:
            raise ValueError("Question alone exceeds the reranker pair limit")
        if len(rows) > 20:
            raise ValueError("Reranker accepts at most 20 hybrid candidates")
        if not rows:
            return []
        snapshots = {row["snapshot_id"] for row in rows}
        if len(snapshots) != 1:
            raise ValueError("Reranker candidates must share one snapshot")
        prepared = []
        for row in rows:
            scored, spans, tokens = self._bounded(query, row)
            prepared.append(
                {
                    **row,
                    "rerank_scored_text": scored,
                    "rerank_source_spans": spans,
                    "rerank_truncated": scored != row["text"],
                    "rerank_original_characters": len(row["text"]),
                    "rerank_scored_characters": len(scored),
                    "rerank_pair_tokens": tokens,
                }
            )
        pairs = [(query, row["rerank_scored_text"]) for row in prepared]
        scores = self.model.predict(
            pairs,
            batch_size=16,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        if len(scores) != len(prepared):
            raise ValueError("Reranker returned the wrong number of scores")
        for row, score in zip(prepared, scores, strict=True):
            value = float(score)
            if not math.isfinite(value):
                raise ValueError("Reranker returned a nonfinite score")
            row["rerank_score"] = value
        return sorted(prepared, key=lambda row: (-row["rerank_score"], row["chunk_id"]))


def load_reranker(model_dir: Path = DEFAULT_MODEL_DIR) -> MiniLMReranker:
    return MiniLMReranker(model_dir)


def prepare_reranker(model_dir: Path = DEFAULT_MODEL_DIR) -> dict:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import HfHubHTTPError

    manifest = _manifest()
    try:
        snapshot_download(
            repo_id=manifest["model"],
            revision=manifest["revision"],
            local_dir=model_dir,
            allow_patterns=list(manifest["files"]),
            max_workers=4,
        )
    except (OSError, ValueError, HfHubHTTPError) as error:
        raise ValueError(f"Could not prepare pinned reranker at {model_dir}: {error}") from error
    return load_reranker(model_dir).profile
