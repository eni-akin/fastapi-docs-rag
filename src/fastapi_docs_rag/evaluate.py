"""Validate source-backed drafts and compare retrieval without claiming ground truth."""

import hashlib
import platform
import time
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from math import log2
from pathlib import Path
from uuid import UUID

from fastapi_docs_rag.manifest import json_hash
from fastapi_docs_rag.retrieve import search


def validate_development_set(connection, snapshot_id: str, dataset: dict) -> dict:
    try:
        if dataset.get("version") == 2:
            return _validate_v2(connection, UUID(str(snapshot_id)), dataset)
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


def _validate_v2(connection, snapshot_id: UUID, dataset: dict) -> dict:
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
        dataset["manifest_hash"] != snapshot["manifest_hash"]
        or sorted((d["url"], d["content_hash"]) for d in dataset["corpus"]) != corpus
    ):
        raise ValueError("Question set does not match the snapshot corpus")
    documents = {row["source_url"]: row["document"] for row in rows}
    questions = dataset["questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("Question set must contain records")
    identifiers = set()
    reviews = Counter()
    categories = Counter()

    def check_evidence(evidence, expected_grade):
        document = documents.get(evidence["source_url"])
        if document is None or document["content_hash"] != evidence["document_hash"]:
            raise ValueError("Evidence document is absent or has a different content hash")
        index, start, end = (evidence[k] for k in ("block_index", "start", "end"))
        if any(type(value) is not int for value in (index, start, end)) or not 0 <= index < len(
            document["blocks"]
        ):
            raise ValueError("Evidence block index must refer to a captured block")
        block = document["blocks"][index]
        if (
            not 0 <= start < end <= len(block["text"])
            or block["text"][start:end] != evidence["text"]
            or block["section_anchor"] != evidence["section_anchor"]
            or block["variants"] != evidence["variants"]
            or type(evidence["grade"]) is not int
            or evidence["grade"] != expected_grade
        ):
            raise ValueError("Evidence span, variant, anchor or grade does not match source")

    for question in questions:
        identifier = question["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("Question IDs must be unique nonempty strings")
        identifiers.add(identifier)
        category = question["category"]
        if category not in {"direct_lookup", "paraphrase", "multi_section", "unsupported"}:
            raise ValueError(f"Invalid question category: {identifier}")
        categories[category] += 1
        if (
            question["split"] != "development"
            or not isinstance(question["family"], str)
            or not question["family"]
            or not isinstance(question["question"], str)
            or not question["question"].strip()
            or len(question["question"]) > 2000
            or type(question["answerable"]) is not bool
            or question["answerable"] == (category == "unsupported")
        ):
            raise ValueError(f"Invalid development question: {identifier}")
        review = question["review"]
        if review["status"] not in {"draft", "approved", "needs_changes"}:
            raise ValueError("Unknown human review status")
        if review["status"] == "approved":
            if not isinstance(review["reviewer"], str) or not review["reviewer"].strip():
                raise ValueError("Approved labels require a human reviewer")
            date = datetime.fromisoformat(review["reviewed_at"])
            if date.tzinfo is None:
                raise ValueError("Review timestamp must include a timezone")
        reviews[review["status"]] += 1
        groups = question["evidence_groups"]
        facts = question["expected_facts"]
        if not isinstance(groups, list) or not isinstance(facts, list):
            raise ValueError("Facts and evidence groups must be lists")
        if question["answerable"]:
            if not groups or len(groups) != len(facts) or [g["fact"] for g in groups] != facts:
                raise ValueError("Each answerable fact requires a distinct evidence group")
        elif groups or facts or not question["unanswerable_reason"]:
            raise ValueError("Unsupported questions require a reason and no positive evidence")
        group_ids = set()
        for group in groups:
            if not group["id"] or group["id"] in group_ids or not group["fact"].strip():
                raise ValueError("Evidence group IDs and facts must be distinct and nonempty")
            group_ids.add(group["id"])
            if not group["alternatives"]:
                raise ValueError("Evidence group needs at least one alternative")
            for alternative in group["alternatives"]:
                if not alternative:
                    raise ValueError("Evidence alternative needs at least one source span")
                for evidence in alternative:
                    check_evidence(evidence, 2)
        for evidence in question.get("context_evidence", []):
            check_evidence(evidence, 1)
    return {
        "provenance_valid": True,
        "question_count": len(questions),
        "category_counts": dict(categories),
        "review_counts": {
            status: reviews[status] for status in ("draft", "approved", "needs_changes")
        },
        "human_review_complete": reviews["approved"] == len(questions),
    }


def _evidence(question):
    for group in question["evidence_groups"]:
        for alternative in group["alternatives"]:
            yield from alternative
    yield from question.get("context_evidence", [])


def _matching_spans(row, evidence):
    if (
        row["source_url"] != evidence["source_url"]
        or row["document_content_hash"] != evidence["document_hash"]
        or row["variants"] != evidence["variants"]
    ):
        return []
    return [span for span in row["source_spans"] if span["block_index"] == evidence["block_index"]]


def map_question_chunks(question: dict, chunks: list[dict]) -> dict:
    """Map reviewed source spans to all overlapping chunks in one fixed snapshot."""
    grades = {}
    unmapped = []
    for evidence in _evidence(question):
        matches = [
            row["chunk_id"]
            for row in chunks
            if any(
                max(span["start"], evidence["start"]) < min(span["end"], evidence["end"])
                for span in _matching_spans(row, evidence)
            )
        ]
        if not matches:
            unmapped.append(
                {key: evidence[key] for key in ("source_url", "block_index", "start", "end")}
            )
        for chunk_id in matches:
            grades[chunk_id] = max(grades.get(chunk_id, 0), evidence["grade"])
    return {"grades": grades, "unmapped_spans": unmapped}


def _span_covered(evidence: dict, rows: list[dict]) -> bool:
    intervals = sorted(
        (max(span["start"], evidence["start"]), min(span["end"], evidence["end"]))
        for row in rows
        for span in _matching_spans(row, evidence)
        if max(span["start"], evidence["start"]) < min(span["end"], evidence["end"])
    )
    covered_until = evidence["start"]
    for start, end in intervals:
        if start > covered_until:
            break
        covered_until = max(covered_until, end)
    return covered_until >= evidence["end"]


def ranking_metrics(question: dict, rows: list[dict], mapping: dict) -> dict:
    """Evaluate top ten against the fixed mapped positive-chunk set."""
    top = rows[:10]
    if len({row["chunk_id"] for row in top}) != len(top):
        raise ValueError("Ranking contains duplicate chunk IDs")
    if not question["answerable"]:
        return {
            "metric_denominator": 0,
            "returned_candidates": len(top),
            "recall_at_10": None,
            "mrr_at_10": None,
            "ndcg_at_10": None,
            "group_coverage_at_10": None,
            "complete_coverage": None,
            "missing_groups": [],
        }
    grades = mapping["grades"]
    if not grades or mapping["unmapped_spans"]:
        raise ValueError("Positive evidence has unmapped source spans")
    found = {row["chunk_id"] for row in top}
    recall = len(found & grades.keys()) / len(grades)
    reciprocal = next(
        (1 / rank for rank, row in enumerate(top, 1) if grades.get(row["chunk_id"]) == 2), 0
    )
    gains = [2 ** grades.get(row["chunk_id"], 0) - 1 for row in top]
    ideal = sorted((2**grade - 1 for grade in grades.values()), reverse=True)[:10]
    dcg = sum(gain / log2(rank + 1) for rank, gain in enumerate(gains, 1))
    idcg = sum(gain / log2(rank + 1) for rank, gain in enumerate(ideal, 1))
    missing = [
        group["id"]
        for group in question["evidence_groups"]
        if not any(
            all(_span_covered(span, top) for span in alternative)
            for alternative in group["alternatives"]
        )
    ]
    count = len(question["evidence_groups"])
    return {
        "metric_denominator": 1,
        "positive_chunk_count": len(grades),
        "returned_candidates": len(top),
        "recall_at_10": recall,
        "mrr_at_10": reciprocal,
        "ndcg_at_10": dcg / idcg,
        "group_coverage_at_10": (count - len(missing)) / count,
        "complete_coverage": not missing,
        "missing_groups": missing,
    }


def _result_row(row: dict) -> dict:
    fields = (
        "chunk_id",
        "snapshot_id",
        "document_id",
        "source_url",
        "url",
        "title",
        "document_content_hash",
        "evidence_key",
        "section_anchor",
        "heading_path",
        "variants",
        "source_spans",
        "partial_code",
        "input_tokens",
        "score",
        "distance",
        "similarity",
        "keyword_rank",
        "vector_rank",
        "keyword_score",
        "vector_distance",
        "vector_similarity",
    )
    return {**{key: row[key] for key in fields if key in row}, "text_excerpt": row["text"][:180]}


def compare_retrieval(
    connection,
    snapshot_id: str,
    dataset: dict,
    *,
    embedder=None,
    model_dir: Path = Path("data/models/all-MiniLM-L6-v2"),
    build_stats: dict | None = None,
) -> dict:
    """Run the three modes on one frozen vector snapshot with one encode per question."""
    from fastapi_docs_rag.retrieve import fuse

    run_started_utc = datetime.now(UTC).isoformat()
    validation = validate_development_set(connection, snapshot_id, dataset)
    if dataset["version"] != 2:
        raise ValueError("Three-mode comparison requires version-2 labels")
    snapshot = connection.execute(
        """SELECT state, capability, manifest_hash, fingerprint, profile,
                  document_count, chunk_count FROM rag_snapshots WHERE id=%s""",
        (UUID(str(snapshot_id)),),
    ).fetchone()
    if snapshot["capability"] != "vector_ready":
        raise ValueError("Comparison requires a vector-ready snapshot")
    model_load_started = time.perf_counter()
    if embedder is None:
        from fastapi_docs_rag.embed import load_embeddings

        embedder = load_embeddings(model_dir)
        model_load_seconds = time.perf_counter() - model_load_started
    else:
        model_load_seconds = None
    if snapshot["profile"].get("embedding") != embedder.profile:
        raise ValueError("Snapshot embedding profile differs from the loaded model")
    chunks = connection.execute(
        """SELECT c.id::text AS chunk_id, d.source_url,
                  d.content_hash AS document_content_hash, c.variants, c.source_spans
           FROM rag_chunks c JOIN rag_documents d
             ON d.id=c.document_id AND d.snapshot_id=c.snapshot_id
           WHERE c.snapshot_id=%s""",
        (UUID(str(snapshot_id)),),
    ).fetchall()
    if len(chunks) != snapshot["chunk_count"]:
        raise ValueError("Snapshot chunk count changed during comparison")
    mappings = {q["id"]: map_question_chunks(q, chunks) for q in dataset["questions"]}
    unmapped = {
        key: value["unmapped_spans"] for key, value in mappings.items() if value["unmapped_spans"]
    }
    if unmapped:
        raise ValueError(f"Proposed evidence has unmapped spans: {unmapped}")
    if build_stats is not None:
        build = build_stats.get("vector_snapshot", build_stats)
        if build.get("snapshot_id") != snapshot_id:
            raise ValueError("Build statistics refer to a different snapshot")
        build_stats = build
    started = time.perf_counter()
    questions = []
    for question in dataset["questions"]:
        query = question["question"]
        stage = {}
        clock = time.perf_counter()
        keyword = search(connection, snapshot_id, query, limit=20, mode="keyword")
        stage["keyword_seconds"] = time.perf_counter() - clock
        clock = time.perf_counter()
        vector = search(connection, snapshot_id, query, limit=20, mode="vector", embedder=embedder)
        stage["vector_seconds_including_one_encode"] = time.perf_counter() - clock
        clock = time.perf_counter()
        hybrid = fuse(keyword, vector, 10)
        stage["fusion_seconds"] = time.perf_counter() - clock
        mapping = mappings[question["id"]]
        questions.append(
            {
                "id": question["id"],
                "question": query,
                "family": question["family"],
                "category": question["category"],
                "proposed_answerable": question["answerable"],
                "review": question["review"],
                "expected_facts": question["expected_facts"],
                "proposed_evidence_groups": question["evidence_groups"],
                "mapped_positive_chunks": mapping["grades"],
                "timings": stage,
                "modes": {
                    "keyword": {
                        "metrics": ranking_metrics(question, keyword[:10], mapping),
                        "results": [_result_row(row) for row in keyword[:10]],
                        "candidate_count": len(keyword),
                    },
                    "vector": {
                        "metrics": ranking_metrics(question, vector[:10], mapping),
                        "results": [_result_row(row) for row in vector[:10]],
                        "candidate_count": len(vector),
                    },
                    "hybrid": {
                        "metrics": ranking_metrics(question, hybrid, mapping),
                        "results": [_result_row(row) for row in hybrid],
                        "candidate_count": len({r["chunk_id"] for r in [*keyword, *vector]}),
                    },
                },
            }
        )
    execution_seconds = time.perf_counter() - started
    aggregates = {}
    for category in ("all", "direct_lookup", "paraphrase", "multi_section", "unsupported"):
        selected = [q for q in questions if category == "all" or q["category"] == category]
        aggregates[category] = {}
        for mode in ("keyword", "vector", "hybrid"):
            metrics = [q["modes"][mode]["metrics"] for q in selected]
            positive = [m for m in metrics if m["metric_denominator"]]
            aggregates[category][mode] = {
                "question_count": len(metrics),
                "positive_metric_denominator": len(positive),
                "unsupported_question_count": len(metrics) - len(positive),
                "unsupported_returned_candidates": sum(
                    m["returned_candidates"] for m in metrics if not m["metric_denominator"]
                ),
                **{
                    key: (sum(m[key] for m in positive) / len(positive) if positive else None)
                    for key in (
                        "recall_at_10",
                        "mrr_at_10",
                        "ndcg_at_10",
                        "group_coverage_at_10",
                        "complete_coverage",
                    )
                },
            }
    migration_rows = connection.execute(
        "SELECT name, sha256 FROM rag_schema_migrations ORDER BY name"
    ).fetchall()
    code_hashes = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("evaluate.py", "retrieve.py", "db.py")
    }
    families = Counter(q["family"] for q in questions)
    retrieval_profile = {
        "keyword_candidates": 20,
        "vector_candidates": 20,
        "rrf_constant": 60,
        "final_depth": 10,
    }
    pending = validation["question_count"] - validation["review_counts"]["approved"]
    return {
        "status": "draft_diagnostics" if pending else "reviewed_diagnostics",
        "started_at_utc": run_started_utc,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "interpretation": (
            f"{pending} of {validation['question_count']} labels await human approval. "
            "Retrieval overlap is not answer sufficiency; unsupported questions may still "
            "return neighbors."
        ),
        "snapshot_id": snapshot_id,
        "snapshot_fingerprint": snapshot["fingerprint"],
        "manifest_hash": snapshot["manifest_hash"],
        "corpus_hash": json_hash(dataset["corpus"]),
        "snapshot_document_count": snapshot["document_count"],
        "snapshot_chunk_count": snapshot["chunk_count"],
        "snapshot_profile": snapshot["profile"],
        "profile_hash": json_hash(snapshot["profile"]),
        "dataset_name": dataset["name"],
        "dataset_hash": json_hash(dataset),
        "label_validation": validation,
        "mapping_valid": True,
        "mapping_limitations": (
            "Positive overlap maps labels to chunks; complete fact coverage requires every "
            "character in each span of one alternative across retrieved fragments."
        ),
        "retrieval_profile": retrieval_profile,
        "retrieval_profile_hash": json_hash(retrieval_profile),
        "hybrid_compute": (
            "Reuses the keyword and vector candidate lists; no second encode or search"
        ),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "packages": {
                name: version(name)
                for name in (
                    "sentence-transformers",
                    "transformers",
                    "torch",
                    "psycopg",
                    "tokenizers",
                )
            },
            "code_sha256": code_hashes,
            "schema_migrations": migration_rows,
            "model_load_seconds": model_load_seconds,
            "cold_first_question_seconds": sum(questions[0]["timings"].values()),
            "warmed_remaining_mean_seconds": (
                sum(sum(q["timings"].values()) for q in questions[1:]) / (len(questions) - 1)
                if len(questions) > 1
                else None
            ),
            "execution_seconds": execution_seconds,
            "questions_per_second": len(questions) / execution_seconds,
            "vector_build_stats": build_stats,
        },
        "family_count": len(families),
        "families_with_multiple_questions": {
            family: count for family, count in families.items() if count > 1
        },
        "aggregates": aggregates,
        "questions": questions,
    }


def comparison_markdown(report: dict) -> str:
    runtime = report["runtime"]
    warm = runtime["warmed_remaining_mean_seconds"]

    def fmt(value):
        return "—" if value is None else f"{value:.3f}"

    lines = [
        "# Draft three-mode retrieval comparison",
        "",
        f"Snapshot: `{report['snapshot_id']}`; dataset hash: `{report['dataset_hash']}`.",
        f"Records: {report['label_validation']['question_count']}; human approved: "
        f"{report['label_validation']['review_counts']['approved']}.",
        "",
        report["interpretation"],
        "",
        "| Category | Mode | Positive N | Recall@10 | MRR@10 | nDCG@10 | "
        "Group coverage@10 | Complete coverage |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category, modes in report["aggregates"].items():
        for mode, values in modes.items():
            lines.append(
                f"| {category} | {mode} | {values['positive_metric_denominator']} | "
                f"{fmt(values['recall_at_10'])} | {fmt(values['mrr_at_10'])} | "
                f"{fmt(values['ndcg_at_10'])} | {fmt(values['group_coverage_at_10'])} | "
                f"{fmt(values['complete_coverage'])} |"
            )
    lines += [
        "",
        "The hybrid ranking reuses one keyword and one vector candidate list per "
        "question. The vector stage includes one query encode. Categories include related "
        "questions; family count and repeated families are recorded in JSON.",
        "",
        "## Questions with incomplete proposed fact coverage",
        "",
    ]
    for question in report["questions"]:
        if not question["proposed_answerable"]:
            continue
        missing = {
            mode: value["metrics"]["missing_groups"]
            for mode, value in question["modes"].items()
            if value["metrics"]["missing_groups"]
        }
        if missing:
            lines.append(f"- `{question['id']}` ({question['category']}): {missing}")
    lines += [
        "",
        "## Runtime and provenance",
        "",
        f"- Model load: {runtime['model_load_seconds']} seconds; "
        f"first question: {runtime['cold_first_question_seconds']:.3f} seconds; "
        f"remaining mean: {warm:.3f} seconds."
        if warm is not None
        else f"- Model load: {runtime['model_load_seconds']} seconds; "
        f"first question: {runtime['cold_first_question_seconds']:.3f} seconds; "
        "remaining mean: unavailable (one question).",
        f"- Execution: {report['runtime']['execution_seconds']:.3f} seconds; "
        f"throughput: {report['runtime']['questions_per_second']:.2f} questions/second.",
        f"- Build reuse: {report['runtime']['vector_build_stats']}.",
        f"- Snapshot profile hash: `{report['profile_hash']}`; retrieval profile hash: "
        f"`{report['retrieval_profile_hash']}`; corpus hash: `{report['corpus_hash']}`.",
        "- Full ranks, scores, source spans, missing groups, code and migration hashes "
        "are in the JSON report.",
        "",
    ]
    return "\n".join(lines)


def review_sheet_markdown(dataset: dict) -> str:
    pending = sum(q["review"]["status"] != "approved" for q in dataset["questions"])
    lines = [
        "# Development question review sheet",
        "",
        f"{pending} of {len(dataset['questions'])} records await human approval. The owner "
        "must approve or correct expected facts, answerability, source spans, grades, "
        "alternatives, and sufficiency before the milestone quality gate can pass.",
        "",
    ]
    for question in dataset["questions"]:
        lines += [
            f"## {question['id']} — {question['category']}",
            "",
            f"**Question:** {question['question']}",
            "",
            f"**Proposed answerable:** {question['answerable']}",
            "",
        ]
        for group in question["evidence_groups"]:
            lines.append(f"- Fact `{group['id']}`: {group['fact']}")
            for index, alternative in enumerate(group["alternatives"], 1):
                for evidence in alternative:
                    lines.append(
                        f"  - Alternative {index}: {evidence['source_url']}"
                        f"#{evidence['section_anchor']} block {evidence['block_index']} "
                        f"[{evidence['start']}:{evidence['end']}], grade {evidence['grade']}: "
                        f"{evidence['text'][:140]!r}"
                    )
        if not question["answerable"]:
            lines.append(f"- Proposed reason: {question['unanswerable_reason']}")
        lines += [
            "",
            "Review: [ ] approve  [ ] correct  [ ] mark unsupported; "
            "Reviewer: ______; Date: ______",
            "",
        ]
    return "\n".join(lines)


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
