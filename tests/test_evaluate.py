import copy
import json

import pytest

from fastapi_docs_rag.db import build_vector_snapshot, import_capture, migrate
from fastapi_docs_rag.evaluate import (
    compare_retrieval,
    comparison_markdown,
    keyword_diagnostics,
    validate_development_set,
)
from fastapi_docs_rag.manifest import json_hash


@pytest.fixture
def labeled_snapshot(database, capture_factory):
    migrate(database)
    report, root = capture_factory()
    metadata = json.loads(report.read_text())
    document = json.loads((root / metadata["pages"][0]["parsed_path"]).read_text())
    index = next(i for i, block in enumerate(document["blocks"]) if block["type"] == "code")
    block = document["blocks"][index]
    dataset = {
        "version": 1,
        "name": "test-draft",
        "manifest_hash": metadata["manifest_hash"],
        "corpus": [{"url": document["url"], "content_hash": document["content_hash"]}],
        "questions": [
            {
                "id": "dev-01",
                "family": "routing",
                "split": "development",
                "question": "FastAPI",
                "answerable": True,
                "expected_facts": ["The example creates an application."],
                "review": {"status": "draft", "reviewer": None, "reviewed_at": None},
                "evidence_groups": [
                    {
                        "id": "support",
                        "evidence": [
                            {
                                "source_url": document["url"],
                                "document_hash": document["content_hash"],
                                "section_anchor": block["section_anchor"],
                                "block_index": index,
                                "start": 0,
                                "end": len(block["text"]),
                                "text": block["text"],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    snapshot = import_capture(database, report, root)["snapshot_id"]
    return snapshot, dataset


def test_drafts_are_valid_provenance_but_not_human_ground_truth(database, labeled_snapshot):
    snapshot, dataset = labeled_snapshot
    result = validate_development_set(database, snapshot, dataset)
    assert result["provenance_valid"]
    assert not result["human_review_complete"]
    assert result["review_counts"]["draft"] == 1
    diagnostics = keyword_diagnostics(database, snapshot, dataset)
    assert diagnostics["dataset_hash"] == json_hash(dataset)
    assert diagnostics["questions"][0]["proposed_evidence_overlap"]
    assert diagnostics["questions"][0]["category"] == "proposed_evidence_overlap_needs_review"


@pytest.mark.parametrize(
    "mutation",
    ["text", "index", "anchor", "hash", "corpus", "approval", "missing_name", "empty_name"],
)
def test_invalid_labels_are_rejected(database, labeled_snapshot, mutation):
    snapshot, dataset = labeled_snapshot
    dataset = copy.deepcopy(dataset)
    evidence = dataset["questions"][0]["evidence_groups"][0]["evidence"][0]
    if mutation == "text":
        evidence["text"] = "fabricated"
    elif mutation == "index":
        evidence["block_index"] = -1
    elif mutation == "anchor":
        evidence["section_anchor"] = "invented"
    elif mutation == "hash":
        evidence["document_hash"] = "changed"
    elif mutation == "corpus":
        dataset["manifest_hash"] = "different capture"
    elif mutation == "missing_name":
        dataset.pop("name")
    elif mutation == "empty_name":
        dataset["name"] = " "
    else:
        dataset["questions"][0]["review"]["status"] = "approved"
    with pytest.raises(ValueError):
        validate_development_set(database, snapshot, dataset)


def test_draft_unanswerable_is_not_silently_graded_correct(database, labeled_snapshot):
    snapshot, dataset = labeled_snapshot
    question = dataset["questions"][0]
    question.update(
        {
            "answerable": False,
            "evidence_groups": [],
            "expected_facts": [],
            "unanswerable_reason": "Proposed outside-corpus question.",
        }
    )
    diagnostic = keyword_diagnostics(database, snapshot, dataset)
    assert diagnostic["questions"][0]["category"] == "lexical_matches_for_draft_unanswerable"
    assert not diagnostic["label_validation"]["human_review_complete"]


def test_diagnostic_cli_saves_pending_review_status(
    database, labeled_snapshot, tmp_path, monkeypatch, capsys
):
    from fastapi_docs_rag import cli

    snapshot, dataset = labeled_snapshot
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(dataset))
    output = tmp_path / "diagnostics.json"
    monkeypatch.setenv("RAG_DATABASE_URL", database.info.dsn)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "diagnose-keyword",
            "--snapshot",
            snapshot,
            "--dataset",
            str(path),
            "--output",
            str(output),
        ],
    )
    assert cli.main() == 0
    saved = json.loads(output.read_text())
    assert saved["dataset_hash"] == json_hash(dataset)
    assert not saved["label_validation"]["human_review_complete"]
    assert json.loads(capsys.readouterr().out)["label_validation"]["review_counts"]["draft"] == 1


def test_review_metadata_can_record_a_real_review_without_changing_provenance(
    database, labeled_snapshot
):
    snapshot, dataset = labeled_snapshot
    dataset["questions"][0]["review"] = {
        "status": "approved",
        "reviewer": "Unit-test reviewer",
        "reviewed_at": "2026-11-05T12:00:00+00:00",
    }
    assert validate_development_set(database, snapshot, dataset)["human_review_complete"]


def test_v2_draft_validates_source_variant_grade_and_review(database, labeled_snapshot):
    snapshot, v1 = labeled_snapshot
    dataset = _as_v2(database, snapshot, v1)
    result = validate_development_set(database, snapshot, dataset)
    assert result["category_counts"] == {"direct_lookup": 1}
    assert not result["human_review_complete"]
    question = dataset["questions"][0]
    group = question["evidence_groups"][0]
    group["alternatives"][0][0]["grade"] = 1
    with pytest.raises(ValueError, match="grade"):
        validate_development_set(database, snapshot, dataset)
    group["alternatives"][0][0]["grade"] = True
    with pytest.raises(ValueError, match="grade"):
        validate_development_set(database, snapshot, dataset)
    group["alternatives"][0][0]["grade"] = 2
    question["review"] = {"status": "approved", "reviewer": None, "reviewed_at": None}
    with pytest.raises(ValueError, match="reviewer"):
        validate_development_set(database, snapshot, dataset)
    question["review"]["reviewer"] = "Fixture reviewer"
    question["review"]["reviewed_at"] = "2026-11-11T12:00:00"
    with pytest.raises(ValueError, match="timezone"):
        validate_development_set(database, snapshot, dataset)


def _as_v2(database, snapshot, v1):
    dataset = copy.deepcopy(v1)
    dataset["version"] = 2
    question = dataset["questions"][0]
    question["category"] = "direct_lookup"
    group = question["evidence_groups"][0]
    group["fact"] = question["expected_facts"][0]
    document = database.execute(
        "SELECT document FROM rag_documents WHERE snapshot_id=%s", (snapshot,)
    ).fetchone()["document"]
    block = document["blocks"][group["evidence"][0]["block_index"]]
    group["alternatives"] = [[{**group["evidence"][0], "variants": block["variants"], "grade": 2}]]
    del group["evidence"]
    return dataset


def test_one_question_comparison_and_cli_share_one_query_encode(
    database, labeled_snapshot, monkeypatch, tmp_path, capsys
):
    from fastapi_docs_rag import cli

    keyword_snapshot, v1 = labeled_snapshot
    dataset = _as_v2(database, keyword_snapshot, v1)

    class StubEmbeddings:
        profile = {
            "model": "test",
            "revision": "fixture",
            "files": {"weights": "fixture"},
            "pooling": "mean",
            "normalization": "l2",
            "dtype": "float32",
            "dimension": 384,
            "max_input_tokens": 256,
            "batch_size": 32,
            "license": "Apache-2.0",
        }

        def __init__(self):
            self.calls = []

        def encode(self, texts):
            self.calls.append(texts)
            return [[1.0] + [0.0] * 383 for _ in texts]

    embedder = StubEmbeddings()
    vector = build_vector_snapshot(database, keyword_snapshot, embedder)["snapshot_id"]
    embedder.calls.clear()
    report = compare_retrieval(database, vector, dataset, embedder=embedder)
    assert embedder.calls == [["FastAPI"]]
    assert report["status"] == "draft_diagnostics"
    assert report["aggregates"]["all"]["hybrid"]["positive_metric_denominator"] == 1
    assert "remaining mean: unavailable" in comparison_markdown(report)
    path = tmp_path / "comparison.json"
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(dataset))
    monkeypatch.setenv("RAG_DATABASE_URL", database.info.dsn)
    monkeypatch.setattr("fastapi_docs_rag.embed.load_embeddings", lambda _: embedder)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rag",
            "compare-retrieval",
            "--snapshot",
            vector,
            "--dataset",
            str(labels),
            "--output",
            str(path),
        ],
    )
    assert cli.main() == 0
    assert embedder.calls == [["FastAPI"], ["FastAPI"]]
    assert path.exists() and path.with_suffix(".md").exists()
    assert path.with_name("comparison-review.md").exists()
    assert json.loads(capsys.readouterr().out)["label_validation"]["review_counts"]["draft"] == 1
