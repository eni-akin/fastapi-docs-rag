"""Validate draft label provenance and inspect keyword failures without inventing ground truth."""

from collections import Counter
from datetime import datetime
from uuid import UUID

from fastapi_docs_rag.manifest import json_hash
from fastapi_docs_rag.retrieve import search


def validate_development_set(connection, snapshot_id: str, dataset: dict) -> dict:
    try:
        return _validate_labels(connection, UUID(str(snapshot_id)), dataset)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError("Malformed development question/evidence record") from error


def _validate_labels(connection, snapshot_id: UUID, dataset: dict) -> dict:
    if not isinstance(dataset.get("name"), str) or not dataset["name"].strip():
        raise ValueError("Question set requires a nonempty name")
    snapshot = connection.execute(
        "SELECT state, manifest_hash FROM rag_snapshots WHERE id=%s", (snapshot_id,)
    ).fetchone()
    if snapshot is None or snapshot["state"] != "ready":
        raise ValueError("Labels require an existing ready snapshot")
    rows = connection.execute(
        "SELECT source_url, content_hash, document FROM rag_documents WHERE snapshot_id=%s",
        (snapshot_id,),
    ).fetchall()
    corpus = sorted((row["source_url"], row["content_hash"]) for row in rows)
    if (
        dataset["version"] != 1
        or dataset["manifest_hash"] != snapshot["manifest_hash"]
        or sorted((d["url"], d["content_hash"]) for d in dataset["corpus"]) != corpus
    ):
        raise ValueError("Question set does not match the snapshot corpus")
    documents = {row["source_url"]: row["document"] for row in rows}
    questions = dataset["questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("Question set must contain records")
    identifiers = set()
    reviews = Counter()
    for question in questions:
        identifier = question["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("Question IDs must be unique nonempty strings")
        identifiers.add(identifier)
        if (
            question["split"] != "development"
            or not isinstance(question["family"], str)
            or not question["family"]
            or not isinstance(question["question"], str)
            or not question["question"].strip()
            or len(question["question"]) > 2000
            or type(question["answerable"]) is not bool
        ):
            raise ValueError(f"Invalid development question: {identifier}")
        review = question["review"]
        if review["status"] not in {"draft", "approved", "needs_changes"}:
            raise ValueError("Unknown human review status")
        if review["status"] == "approved":
            if (
                not isinstance(review["reviewer"], str)
                or not review["reviewer"].strip()
                or not review["reviewed_at"]
            ):
                raise ValueError("Approved labels require a human reviewer and review timestamp")
            date = datetime.fromisoformat(review["reviewed_at"])
            if date.tzinfo is None:
                raise ValueError("Review timestamp must include a timezone")
        reviews[review["status"]] += 1
        groups = question["evidence_groups"]
        facts = question["expected_facts"]
        if (
            not isinstance(groups, list)
            or not isinstance(facts, list)
            or any(not isinstance(fact, str) or not fact.strip() for fact in facts)
        ):
            raise ValueError("Expected facts and evidence groups must be lists")
        if question["answerable"]:
            if not groups or not facts:
                raise ValueError("Answerable drafts require proposed facts and evidence")
        elif groups or facts or not question["unanswerable_reason"]:
            raise ValueError("Unanswerable drafts need a reason and no positive evidence")
        for group in groups:
            if not group["evidence"]:
                raise ValueError("An evidence group must contain source spans")
            for evidence in group["evidence"]:
                document = documents.get(evidence["source_url"])
                if document is None or document["content_hash"] != evidence["document_hash"]:
                    raise ValueError("Evidence document is absent or has a different content hash")
                index, start, end = (evidence[k] for k in ("block_index", "start", "end"))
                if any(
                    type(value) is not int for value in (index, start, end)
                ) or not 0 <= index < len(document["blocks"]):
                    raise ValueError("Evidence block index must refer to a captured block")
                block = document["blocks"][index]
                if (
                    not 0 <= start < end <= len(block["text"])
                    or block["text"][start:end] != evidence["text"]
                    or block["section_anchor"] != evidence["section_anchor"]
                ):
                    raise ValueError("Evidence span or source anchor does not match captured text")
    return {
        "provenance_valid": True,
        "question_count": len(questions),
        "review_counts": {
            status: reviews[status] for status in ("draft", "approved", "needs_changes")
        },
        "human_review_complete": reviews["approved"] == len(questions),
    }


def keyword_diagnostics(connection, snapshot_id: str, dataset: dict) -> dict:
    validation = validate_development_set(connection, snapshot_id, dataset)
    results = []
    for question in dataset["questions"]:
        matches = search(connection, snapshot_id, question["question"], limit=10)
        evidence = [e for group in question["evidence_groups"] for e in group["evidence"]]
        overlaps = any(
            row["source_url"] == label["source_url"]
            and row["document_content_hash"] == label["document_hash"]
            and span["block_index"] == label["block_index"]
            and max(span["start"], label["start"]) < min(span["end"], label["end"])
            for row in matches
            for span in row["source_spans"]
            for label in evidence
        )
        if not question["answerable"]:
            category = (
                "lexical_matches_for_draft_unanswerable"
                if matches
                else ("no_matches_for_draft_unanswerable")
            )
        elif not matches:
            category = "no_keyword_matches"
        elif overlaps:
            category = "proposed_evidence_overlap_needs_review"
        else:
            category = "proposed_evidence_not_in_top10"
        results.append(
            {
                "id": question["id"],
                "question": question["question"],
                "proposed_answerable": question["answerable"],
                "proposed_evidence_overlap": overlaps,
                "category": category,
                "matches": [
                    {
                        key: row[key]
                        for key in ("chunk_id", "url", "score", "source_spans", "partial_code")
                    }
                    for row in matches
                ],
            }
        )
    return {
        "snapshot_id": snapshot_id,
        "dataset": dataset["name"],
        "label_validation": validation,
        "dataset_hash": json_hash(dataset),
        "interpretation": (
            "Lexical/proposed-span diagnostics only; no semantic answer-quality claim."
        ),
        "categories": dict(Counter(row["category"] for row in results)),
        "questions": results,
    }
