"""Operator commands for the documentation corpus."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
import psycopg

from fastapi_docs_rag.artifacts import write_json
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
    commands.add_parser("migrate", help="Apply checked PostgreSQL schema migrations")
    command = commands.add_parser("import-capture", help="Build or reuse a keyword-only snapshot")
    command.add_argument("--report", type=Path, required=True)
    command.add_argument("--artifacts", type=Path, default=Path("data"))
    command = commands.add_parser("search", help="Inspect keyword matches in a ready snapshot")
    command.add_argument("--snapshot", required=True)
    command.add_argument("--query", required=True)
    command.add_argument("--mode", choices=["keyword"], default="keyword")
    command.add_argument("--limit", type=int, default=10)
    command.add_argument("--json", action="store_true")
    command = commands.add_parser(
        "diagnose-keyword", help="Check label provenance and inspect misses"
    )
    command.add_argument("--snapshot", required=True)
    command.add_argument("--dataset", type=Path, default=Path("evals/development-draft.json"))
    command.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    async def run():
        limits = FetchLimits()
        async with httpx.AsyncClient(
            timeout=limits.request_timeout,
            headers={"user-agent": "fastapi-docs-rag/0.1 (documentation capture)"},
            trust_env=False,
        ) as client:
            return await capture(arguments.manifest, arguments.output, client, limits)

    try:
        if arguments.command != "capture":
            with connect_database() as connection:
                if arguments.command == "migrate":
                    result = {"applied": migrate(connection)}
                elif arguments.command == "import-capture":
                    result = import_capture(connection, arguments.report, arguments.artifacts)
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
                else:
                    rows = search(
                        connection,
                        arguments.snapshot,
                        arguments.query,
                        arguments.limit,
                        arguments.mode,
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
                            print(f"\n{index}. {row['title']} | score {row['score']:.6f}")
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
