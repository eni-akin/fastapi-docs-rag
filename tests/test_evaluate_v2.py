import math

import pytest

from fastapi_docs_rag.evaluate import map_question_chunks, ranking_metrics


def label(start, end, grade=2):
    return {
        "source_url": "https://fastapi.tiangolo.com/tutorial/testing/",
        "document_hash": "hash",
        "section_anchor": "testing",
        "block_index": 3,
        "start": start,
        "end": end,
        "text": "x" * (end - start),
        "variants": [],
        "grade": grade,
    }


def row(chunk_id, start, end):
    return {
        "chunk_id": chunk_id,
        "source_url": "https://fastapi.tiangolo.com/tutorial/testing/",
        "document_content_hash": "hash",
        "variants": [],
        "source_spans": [{"block_index": 3, "start": start, "end": end}],
    }


def question(groups, context=()):
    return {
        "answerable": True,
        "evidence_groups": [
            {"id": f"fact-{i}", "fact": "fact", "alternatives": alts}
            for i, alts in enumerate(groups, 1)
        ],
        "context_evidence": list(context),
    }


def test_hand_computed_recall_mrr_ndcg_and_context_grade():
    direct = row("direct", 0, 5)
    context = row("context", 10, 15)
    q = question([[[label(0, 5)]]], [label(10, 15, 1)])
    mapping = map_question_chunks(q, [direct, context])
    assert mapping == {"grades": {"direct": 2, "context": 1}, "unmapped_spans": []}
    metrics = ranking_metrics(q, [context, direct], mapping)
    assert metrics["recall_at_10"] == 1
    assert metrics["mrr_at_10"] == 0.5
    assert metrics["ndcg_at_10"] == pytest.approx((1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3)))
    assert metrics["group_coverage_at_10"] == 1
    assert metrics["complete_coverage"]


def test_complete_coverage_requires_union_of_fragments_and_all_groups():
    left, right, other = row("left", 0, 2), row("right", 2, 5), row("other", 10, 13)
    q = question([[[label(0, 5)]], [[label(10, 13)]]])
    mapping = map_question_chunks(q, [left, right, other])
    partial = ranking_metrics(q, [left, other], mapping)
    assert partial["recall_at_10"] == 2 / 3
    assert partial["group_coverage_at_10"] == 0.5
    assert partial["missing_groups"] == ["fact-1"]
    assert not partial["complete_coverage"]
    complete = ranking_metrics(q, [left, right, other], mapping)
    assert complete["group_coverage_at_10"] == 1
    assert complete["complete_coverage"]


def test_alternative_can_cover_fact_without_first_span():
    q = question([[[label(0, 5)], [label(10, 13)]]])
    rows = [row("first", 0, 5), row("alternative", 10, 13)]
    mapping = map_question_chunks(q, rows)
    assert ranking_metrics(q, [rows[1]], mapping)["group_coverage_at_10"] == 1
    assert ranking_metrics(q, [rows[1]], mapping)["recall_at_10"] == 0.5


def test_source_variant_and_document_must_match():
    q = question([[[label(0, 5)]]])
    wrong = row("wrong", 0, 5) | {"variants": [{"label": "old Python"}]}
    assert map_question_chunks(q, [wrong])["unmapped_spans"]
    with pytest.raises(ValueError, match="unmapped"):
        ranking_metrics(q, [wrong], map_question_chunks(q, [wrong]))


def test_unsupported_has_no_positive_metric_denominator():
    q = {"answerable": False, "evidence_groups": []}
    metrics = ranking_metrics(q, [row("neighbor", 0, 5)], {"grades": {}, "unmapped_spans": []})
    assert metrics["metric_denominator"] == 0
    assert metrics["returned_candidates"] == 1
    assert metrics["recall_at_10"] is None
    assert metrics["complete_coverage"] is None


def test_duplicate_ranked_chunk_is_rejected():
    q = question([[[label(0, 5)]]])
    match = row("same", 0, 5)
    with pytest.raises(ValueError, match="duplicate"):
        ranking_metrics(q, [match, match], map_question_chunks(q, [match]))
