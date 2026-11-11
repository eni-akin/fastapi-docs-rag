import json
import math
from pathlib import Path

import pytest

from fastapi_docs_rag.evaluate import (
    calibrate_raw_scores,
    context_coverage,
    map_question_chunks,
    ranking_metrics,
    selected_rerank_score,
)
from fastapi_docs_rag.manifest import json_hash


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


def test_context_coverage_uses_full_alternative_union_not_any_overlap():
    q = question([[[label(0, 5)]], [[label(10, 13)]]])
    partial = context_coverage(q, [row("left", 0, 2), row("other", 10, 13)])
    assert partial["selected_entries"] == 2
    assert partial["group_coverage"] == 0.5
    assert partial["missing_groups"] == ["fact-1"]
    complete = context_coverage(q, [row("left", 0, 2), row("right", 2, 5), row("other", 10, 13)])
    assert complete["complete_coverage"]
    assert context_coverage({"answerable": False}, []) == {
        "metric_denominator": 0,
        "selected_entries": 0,
        "group_coverage": None,
        "complete_coverage": None,
        "missing_groups": [],
    }


def test_selected_score_ignores_highest_candidate_skipped_by_context():
    ranked = [
        {"chunk_id": "skipped", "rerank_score": 9.0},
        {"chunk_id": "kept", "rerank_score": 2.0},
        {"chunk_id": "merged", "rerank_score": 3.0},
    ]
    assert selected_rerank_score(ranked, [{"chunk_ids": ["kept", "merged"]}]) == {
        "chunk_id": "merged",
        "raw_score": 3.0,
    }
    assert selected_rerank_score(ranked, []) == {"chunk_id": None, "raw_score": None}
    with pytest.raises(ValueError, match="absent"):
        selected_rerank_score(ranked, [{"chunk_ids": ["invented"]}])


def test_raw_cutoff_sweep_ties_endpoints_and_empty_evidence():
    cases = [
        {"answerable": True, "score": 2.0, "evidence_count": 1},
        {"answerable": False, "score": 2.0, "evidence_count": 1},
        {"answerable": True, "score": -1.0, "evidence_count": 0},
        {"answerable": False, "score": None, "evidence_count": 0},
    ]
    result = calibrate_raw_scores(cases)
    assert result["status"] == "unvalidated"
    assert [(point["cutoff_kind"], point["raw_score_cutoff"]) for point in result["sweep"]] == [
        ("accept_all_nonempty", None),
        ("score", 2.0),
        ("reject_all", None),
    ]
    assert result["sweep"][0]["unsupported_accepted"] == 1
    assert result["sweep"][0]["answerable_rejected"] == 1
    assert result["sweep"][1]["unsupported_accepted"] == 1  # equal scores accept together
    assert result["sweep"][-1]["answerable_rejected"] == 2
    assert result["proposal"]["cutoff_kind"] == "reject_all"
    assert result["proposal"]["unsupported_denominator"] == 2


def test_raw_cutoff_prefers_observed_separator_when_it_reduces_both_errors():
    result = calibrate_raw_scores(
        [
            {"answerable": True, "score": 3.0, "evidence_count": 1},
            {"answerable": True, "score": 2.0, "evidence_count": 1},
            {"answerable": False, "score": 1.0, "evidence_count": 1},
            {"answerable": False, "score": -1.0, "evidence_count": 1},
        ]
    )
    assert result["proposal"]["raw_score_cutoff"] == 2.0
    assert result["proposal"]["unsupported_acceptance_rate"] == 0
    assert result["proposal"]["answerable_rejection_rate"] == 0


@pytest.mark.parametrize(
    "cases",
    [
        [{"answerable": True, "score": 1.0, "evidence_count": 1}],
        [{"answerable": False, "score": 1.0, "evidence_count": 1}],
    ],
)
def test_calibration_requires_both_classes(cases):
    with pytest.raises(ValueError, match="both answerable and unsupported"):
        calibrate_raw_scores(cases)


@pytest.mark.parametrize(
    "bad_case",
    [
        {"answerable": 1, "score": 1.0, "evidence_count": 1},
        {"answerable": True, "score": 1.0, "evidence_count": -1},
        {"answerable": True, "score": 1.0, "evidence_count": 1.5},
        {"answerable": True, "score": float("nan"), "evidence_count": 1},
    ],
)
def test_calibration_rejects_invalid_inputs(bad_case):
    with pytest.raises(ValueError, match="Calibration|evidence"):
        calibrate_raw_scores([bad_case, {"answerable": False, "score": 0.0, "evidence_count": 1}])


def test_retained_draft_policy_identifies_exact_report_and_selected_scores():
    path = Path(__file__).resolve().parents[1] / "reports/milestone-4-retrieval-draft.json"
    report = json.loads(path.read_text())
    policy = report.pop("sufficiency_policy_proposal")
    assert policy["report_identity_scope"] == "report JSON excluding sufficiency_policy_proposal"
    assert policy["report_identity"] == json_hash(report)
    assert policy["references"]["context_profile_hash"] == json_hash(report["context_profile"])
    assert policy["status"] == "unvalidated"
    for question in report["questions"]:
        context = question["selected_context"]
        selected = {chunk_id for entry in context["entries"] for chunk_id in entry["chunk_ids"]}
        scored = [
            row
            for row in question["modes"]["hybrid_rerank"]["results"]
            if row["chunk_id"] in selected
        ]
        assert context["selected_raw_rerank_score"] == (
            max(row["rerank_score"] for row in scored) if scored else None
        )
        assert context["scored_chunk_id"] in selected
