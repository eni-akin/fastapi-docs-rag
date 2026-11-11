import math

import pytest

from fastapi_docs_rag.rerank import MiniLMReranker, _source_prefix
from fastapi_docs_rag.retrieve import search


class CharacterTokenizer:
    def __call__(self, question, passage=None, **kwargs):
        if passage is None:
            return {
                "offset_mapping": [(i, i + 1) for i in range(len(question))],
                "input_ids": list(range(len(question))),
            }
        return {"input_ids": list(range(len(question) + len(passage) + 3))}


class Model:
    def __init__(self, scores):
        self.scores = scores
        self.pairs = None

    def predict(self, pairs, **kwargs):
        assert kwargs["batch_size"] <= 16
        self.pairs = pairs
        return self.scores


def reranker(scores, limit=20):
    instance = MiniLMReranker.__new__(MiniLMReranker)
    instance.tokenizer = CharacterTokenizer()
    instance.model = Model(scores)
    instance.limit = limit
    return instance


def row(chunk_id, text, spans=None, snapshot="one"):
    return {
        "chunk_id": chunk_id,
        "snapshot_id": snapshot,
        "text": text,
        "source_spans": spans or [{"block_index": 2, "start": 4, "end": 4 + len(text)}],
        "score": 0.031,
        "keyword_rank": 1,
    }


def test_pair_boundary_query_and_stable_raw_logit_ties():
    ranker = reranker([-2.0, -2.0], limit=12)
    rows = [row("b", "évidence"), row("a", "code")]
    ranked = ranker.rerank("q", rows)
    assert [item["chunk_id"] for item in ranked] == ["a", "b"]
    assert all(item["score"] == 0.031 and item["rerank_score"] == -2.0 for item in ranked)
    assert ranker.model.pairs == [("q", "évidence"), ("q", "code")]
    assert ranked[0]["rerank_pair_tokens"] == 1 + len("code") + 3
    with pytest.raises(ValueError, match="Question alone"):
        ranker.rerank("x" * 10, rows)
    assert ranker.model.pairs == [("q", "évidence"), ("q", "code")]


def test_long_code_prefix_keeps_exact_source_spans_and_complete_lines():
    text = "first\nsecond\nthird\n"
    ranker = reranker([1.25], limit=17)
    result = ranker.rerank("q", [row("a", text)])[0]
    assert result["rerank_scored_text"] == "first\nsecond\n"
    assert result["rerank_source_spans"] == [{"block_index": 2, "start": 4, "end": 17}]
    assert result["rerank_truncated"] is True
    assert result["rerank_pair_tokens"] <= 17
    assert result["text"] == text


def test_prefix_across_block_separator_has_no_unmapped_separator():
    original = row(
        "a",
        "one\n\ntwo",
        [{"block_index": 1, "start": 0, "end": 3}, {"block_index": 2, "start": 4, "end": 7}],
    )
    assert _source_prefix(original, 4) == ("one", original["source_spans"][:1])
    assert _source_prefix(original, 7) == (
        "one\n\ntw",
        [{"block_index": 1, "start": 0, "end": 3}, {"block_index": 2, "start": 4, "end": 6}],
    )


def test_invalid_scores_counts_and_snapshots():
    for scores in ([math.nan], [], [1.0, 2.0]):
        with pytest.raises(ValueError):
            reranker(scores).rerank("q", [row("a", "text")])
    with pytest.raises(ValueError, match="one snapshot"):
        reranker([1, 2]).rerank("q", [row("a", "text"), row("b", "text", snapshot="two")])


def test_hybrid_rerank_uses_twenty_candidates_and_preserves_other_modes(monkeypatch):
    from uuid import uuid4

    from fastapi_docs_rag import retrieve

    snapshot = str(uuid4())

    class Connection:
        def execute(self, statement, parameters):
            return self

        def fetchone(self):
            return {
                "state": "ready",
                "capability": "vector_ready",
                "profile": {"embedding": "same"},
            }

    class Embedder:
        profile = "same"

        def encode(self, texts):
            assert texts == ["q"]
            return [[1.0] + [0.0] * 383]

    class Ranker:
        def rerank(self, query, rows):
            assert query == "q" and len(rows) == 20
            return [{**item, "rerank_score": float(index)} for index, item in enumerate(rows)]

    monkeypatch.setattr(
        retrieve,
        "_keyword",
        lambda connection, snapshot, query, limit: [
            {"chunk_id": str(i), "snapshot_id": str(snapshot), "score": 1.0} for i in range(limit)
        ],
    )
    monkeypatch.setattr(retrieve, "_vector", lambda *args: [])
    rows = search(
        Connection(),
        snapshot,
        "q",
        limit=50,
        mode="hybrid-rerank",
        embedder=Embedder(),
        reranker=Ranker(),
    )
    assert len(rows) == 20 and rows[0]["score"] == 1 / 61
    assert {item["hybrid_rank"] for item in rows} == set(range(1, 21))
    assert len(search(Connection(), snapshot, "q", mode="hybrid", embedder=Embedder())) == 10
