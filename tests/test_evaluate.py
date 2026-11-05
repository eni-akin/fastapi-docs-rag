import copy
import json

import pytest

from fastapi_docs_rag.db import import_capture, migrate
from fastapi_docs_rag.evaluate import keyword_diagnostics, validate_development_set
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
