"""Operator commands for the documentation corpus."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
import psycopg

from fastapi_docs_rag.db import connect_database, import_capture, migrate
from fastapi_docs_rag.fetch import FetchLimits
from fastapi_docs_rag.ingest import capture


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
                else:
                    result = import_capture(connection, arguments.report, arguments.artifacts)
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
