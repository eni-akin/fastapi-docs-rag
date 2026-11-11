"""Operator commands for the documentation corpus."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
import psycopg

from fastapi_docs_rag.artifacts import write_bytes, write_json
from fastapi_docs_rag.db import connect_database, import_capture, migrate
from fastapi_docs_rag.evaluate import keyword_diagnostics
from fastapi_docs_rag.fetch import FetchLimits
from fastapi_docs_rag.ingest import capture
from fastapi_docs_rag.retrieve import search


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the captured FastAPI documentation corpus")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("capture", help="Download, parse, validate, and report")
    command.add_argument(
        "--manifest", type=Path, default=Path("corpus/manifests/tutorial-seed.json")
    )
    command.add_argument("--output", type=Path, default=Path("data"))
    command.add_argument(
        "--retained-report", type=Path, help="Reuse unchanged pages from a prior capture"
    )
    command.add_argument(
        "--retained-artifacts", type=Path, help="Artifact root for the prior capture"
    )
    commands.add_parser("migrate", help="Apply checked PostgreSQL schema migrations")
    commands.add_parser(
        "prepare-embeddings", help="Download and verify the pinned local MiniLM model"
    )
    command = commands.add_parser(
        "prepare-reranker", help="Download and verify the pinned local cross-encoder"
    )
    command.add_argument(
        "--model-dir", type=Path, default=Path("data/models/ms-marco-MiniLM-L6-v2")
    )
    command = commands.add_parser(
        "prepare-context-tokenizer", help="Download only the pinned Qwen tokenizer assets"
    )
    command.add_argument(
        "--model-dir", type=Path, default=Path("data/models/qwen2.5-1.5b-tokenizer")
    )
    command = commands.add_parser("import-capture", help="Build or reuse a keyword-only snapshot")
    command.add_argument("--report", type=Path, required=True)
    command.add_argument("--artifacts", type=Path, default=Path("data"))
    command = commands.add_parser("embed-snapshot", help="Build or reuse a vector-ready snapshot")
    command.add_argument("--snapshot", required=True, help="Ready keyword snapshot UUID")
    command.add_argument("--model-dir", type=Path, default=Path("data/models/all-MiniLM-L6-v2"))
    command = commands.add_parser("search", help="Inspect matches in a ready snapshot")
    command.add_argument("--snapshot", required=True)
    command.add_argument("--query", required=True)
    command.add_argument(
        "--mode", choices=["keyword", "vector", "hybrid", "hybrid-rerank"], default="keyword"
    )
    command.add_argument("--limit", type=int, default=10)
    command.add_argument("--model-dir", type=Path, default=Path("data/models/all-MiniLM-L6-v2"))
    command.add_argument(
        "--reranker-dir", type=Path, default=Path("data/models/ms-marco-MiniLM-L6-v2")
    )
    command.add_argument("--json", action="store_true")
    command = commands.add_parser("context", help="Print a bounded, source-checked evidence bundle")
    command.add_argument("--snapshot", required=True)
    command.add_argument("--query", required=True)
    command.add_argument("--model-dir", type=Path, default=Path("data/models/all-MiniLM-L6-v2"))
    command.add_argument(
        "--reranker-dir", type=Path, default=Path("data/models/ms-marco-MiniLM-L6-v2")
    )
    command.add_argument(
        "--tokenizer-dir", type=Path, default=Path("data/models/qwen2.5-1.5b-tokenizer")
    )
    command.add_argument("--json", action="store_true")
    command = commands.add_parser(
        "diagnose-keyword", help="Check label provenance and inspect misses"
    )
    command.add_argument("--snapshot", required=True)
    command.add_argument("--dataset", type=Path, default=Path("evals/development-draft.json"))
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser(
        "compare-retrieval", help="Draft keyword/vector/hybrid comparison on one vector snapshot"
    )
    command.add_argument("--snapshot", required=True)
    command.add_argument("--dataset", type=Path, default=Path("evals/development-v2-draft.json"))
    command.add_argument("--output", type=Path, required=True, help="JSON report path")
    command.add_argument("--model-dir", type=Path, default=Path("data/models/all-MiniLM-L6-v2"))
    command.add_argument(
        "--build-report", type=Path, help="Matching vector build JSON for reuse counts"
    )
    arguments = parser.parse_args()
    if arguments.command == "capture" and (arguments.retained_artifacts is None) != (
        arguments.retained_report is None
    ):
        parser.error("--retained-report and --retained-artifacts must be used together")

    async def run():
        limits = FetchLimits()
        async with httpx.AsyncClient(
            timeout=limits.request_timeout,
            headers={"user-agent": "fastapi-docs-rag/0.1 (documentation capture)"},
            trust_env=False,
        ) as client:
            retained = {}
            if arguments.retained_report is not None:
                retained["retained_report_path"] = arguments.retained_report
            if arguments.retained_artifacts is not None:
                retained["retained_artifact_dir"] = arguments.retained_artifacts
            return await capture(arguments.manifest, arguments.output, client, limits, **retained)

    try:
        if arguments.command == "prepare-embeddings":
            from fastapi_docs_rag.embed import prepare_embeddings

            print(json.dumps(prepare_embeddings(), indent=2))
            return 0
        if arguments.command == "prepare-reranker":
            from fastapi_docs_rag.rerank import prepare_reranker

            print(json.dumps(prepare_reranker(arguments.model_dir), indent=2))
            return 0
        if arguments.command == "prepare-context-tokenizer":
            from fastapi_docs_rag.context import prepare_context_tokenizer

            print(json.dumps(prepare_context_tokenizer(arguments.model_dir), indent=2))
            return 0
        if arguments.command != "capture":
            with connect_database() as connection:
                if arguments.command == "migrate":
                    result = {"applied": migrate(connection)}
                elif arguments.command == "import-capture":
                    result = import_capture(connection, arguments.report, arguments.artifacts)
                elif arguments.command == "embed-snapshot":
                    from fastapi_docs_rag.db import build_vector_snapshot
                    from fastapi_docs_rag.embed import load_embeddings

                    result = build_vector_snapshot(
                        connection, arguments.snapshot, load_embeddings(arguments.model_dir)
                    )
                elif arguments.command == "diagnose-keyword":
                    dataset = json.loads(arguments.dataset.read_text(encoding="utf-8"))
                    result = keyword_diagnostics(connection, arguments.snapshot, dataset)
                    write_json(arguments.output, result)
                    print(
                        json.dumps(
                            {
                                "report": str(arguments.output),
                                "label_validation": result["label_validation"],
                                "categories": result["categories"],
                            },
                            indent=2,
                        )
                    )
                    return 0
                elif arguments.command == "compare-retrieval":
                    from fastapi_docs_rag.evaluate import (
                        compare_retrieval,
                        comparison_markdown,
                        review_sheet_markdown,
                    )

                    dataset = json.loads(arguments.dataset.read_text(encoding="utf-8"))
                    build = (
                        json.loads(arguments.build_report.read_text(encoding="utf-8"))
                        if arguments.build_report
                        else None
                    )
                    result = compare_retrieval(
                        connection,
                        arguments.snapshot,
                        dataset,
                        model_dir=arguments.model_dir,
                        build_stats=build,
                    )
                    write_json(arguments.output, result)
                    summary = arguments.output.with_suffix(".md")
                    review_sheet = arguments.output.with_name(arguments.output.stem + "-review.md")
                    write_bytes(summary, comparison_markdown(result).encode("utf-8"))
                    write_bytes(review_sheet, review_sheet_markdown(dataset).encode("utf-8"))
                    print(
                        json.dumps(
                            {
                                "report": str(arguments.output),
                                "summary": str(summary),
                                "review_sheet": str(review_sheet),
                                "label_validation": result["label_validation"],
                            },
                            indent=2,
                        )
                    )
                    return 0
                elif arguments.command == "context":
                    from fastapi_docs_rag.context import build_context, load_context_tokenizer

                    rows = search(
                        connection,
                        arguments.snapshot,
                        arguments.query,
                        20,
                        "hybrid-rerank",
                        model_dir=arguments.model_dir,
                        reranker_dir=arguments.reranker_dir,
                    )
                    tokenizer, _ = load_context_tokenizer(arguments.tokenizer_dir)
                    result = build_context(
                        connection, arguments.snapshot, arguments.query, rows, tokenizer=tokenizer
                    )
                    if not arguments.json:
                        print(
                            f"{len(result['entries'])} evidence entries | "
                            f"{result['prompt_tokens']}/{result['profile']['max_input_tokens']} "
                            f"input tokens | snapshot {result['snapshot_id']}"
                        )
                        print("Prompt version: " + result["version"])
                        print("System: " + result["messages"][0]["content"])
                        print("Question: " + result["question"])
                        for entry in result["entries"]:
                            print(f"\n{entry['evidence_id']}. {entry['title']} | {entry['url']}")
                            print(
                                f"document {entry['document_id']} | content hash "
                                f"{entry['document_content_hash']} | raw hash "
                                f"{entry['document_raw_hash']}"
                            )
                            print("chunks: " + ", ".join(entry["chunk_ids"]))
                            print("source spans: " + json.dumps(entry["source_spans"]))
                            print("variants: " + json.dumps(entry["variants"], ensure_ascii=False))
                            print(
                                f"partial code: {entry['partial_code']} | "
                                f"expanded blocks: {entry['expanded_code_blocks']}"
                            )
                            print(entry["text"])
                        print("\nSkipped: " + json.dumps(result["skipped"]))
                        print("Sufficiency: " + result["sufficiency_policy"])
                        return 0
                else:
                    rows = search(
                        connection,
                        arguments.snapshot,
                        arguments.query,
                        arguments.limit,
                        arguments.mode,
                        model_dir=arguments.model_dir,
                        reranker_dir=arguments.reranker_dir,
                    )
                    result = {
                        "snapshot_id": arguments.snapshot,
                        "mode": arguments.mode,
                        "query": arguments.query,
                        "results": rows,
                    }
                    if not arguments.json:
                        print(f"{len(rows)} results | snapshot {arguments.snapshot}")
                        for index, row in enumerate(rows, start=1):
                            label = (
                                "RRF"
                                if arguments.mode == "hybrid"
                                else (
                                    "raw rerank logit"
                                    if arguments.mode == "hybrid-rerank"
                                    else (
                                        "cosine similarity"
                                        if arguments.mode == "vector"
                                        else "score"
                                    )
                                )
                            )
                            displayed = (
                                row["rerank_score"]
                                if arguments.mode == "hybrid-rerank"
                                else row["score"]
                            )
                            print(f"\n{index}. {row['title']} | {label} {displayed:.6f}")
                            if arguments.mode == "vector":
                                print(f"cosine distance: {row['distance']:.6f}")
                            if arguments.mode in {"hybrid", "hybrid-rerank"}:
                                print(
                                    f"keyword rank: {row['keyword_rank']} | "
                                    f"vector rank: {row['vector_rank']} | "
                                    f"keyword score: {row['keyword_score']} | "
                                    f"vector distance: {row['vector_distance']} | "
                                    f"vector similarity: {row['vector_similarity']}"
                                )
                            if arguments.mode == "hybrid-rerank":
                                print(
                                    f"RRF score: {row['score']:.6f} | "
                                    f"pair tokens: {row['rerank_pair_tokens']} | "
                                    f"truncated: {row['rerank_truncated']}"
                                )
                                print(
                                    "scored source spans: " + json.dumps(row["rerank_source_spans"])
                                )
                                print("scored text: " + row["rerank_scored_text"])
                            print(f"chunk {row['chunk_id']} | document {row['document_id']}")
                            print(row["url"])
                            print("heading: " + " > ".join(row["heading_path"]))
                            print("variants: " + " / ".join(v["label"] for v in row["variants"]))
                            print(
                                f"tokens: {row['input_tokens']} | "
                                f"partial code: {row['partial_code']}"
                            )
                            print("source spans: " + json.dumps(row["source_spans"]))
                            print(row["text"])
                        return 0
            print(json.dumps(result, indent=2))
            return 0
        path, report = asyncio.run(run())
    except (ValueError, OSError) as error:
        print(f"Operation failed: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        detail = error.diag.message_primary or "Check RAG_DATABASE_URL and PostgreSQL availability"
        print(f"Database operation failed ({type(error).__name__}): {detail}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Capture interrupted; any report left running is incomplete.", file=sys.stderr)
        return 130
    print(
        f"{report['status']}: {report['pages_succeeded']} succeeded, "
        f"{report['pages_failed']} failed"
    )
    print(f"Report: {path}")
    for page in report["pages"]:
        if page["status"] == "failed":
            print(f"{page['url']} [{page['stage']}]: {page['error']}", file=sys.stderr)
    return 0 if report["status"] == "succeeded" else 1
