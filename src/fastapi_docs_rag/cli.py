"""Operator commands for the documentation corpus."""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from fastapi_docs_rag.fetch import FetchLimits
from fastapi_docs_rag.ingest import capture


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the approved FastAPI documentation corpus"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("capture", help="Download, parse, validate, and report")
    command.add_argument(
        "--manifest", type=Path, default=Path("corpus/manifests/tutorial-seed.json")
    )
    command.add_argument("--output", type=Path, default=Path("data"))
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
        path, report = asyncio.run(run())
    except (ValueError, OSError) as error:
        print(f"Capture could not start or save its report: {error}", file=sys.stderr)
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
