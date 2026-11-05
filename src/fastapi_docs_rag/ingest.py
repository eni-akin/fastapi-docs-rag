"""Capture reports and readable exports, before database indexing is introduced."""

import asyncio
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx

from fastapi_docs_rag.artifacts import write_bytes, write_json
from fastapi_docs_rag.fetch import FetchLimits, fetch_page
from fastapi_docs_rag.manifest import json_hash, load_manifest
from fastapi_docs_rag.parse import PARSER_VERSION, parse_page, validate_page


def render_markdown(document: dict) -> str:
    lines = [f"Source: {document['url']}", f"Content SHA-256: {document['content_hash']}", ""]
    variant = None
    callout = None
    section = None
    for block in document["blocks"]:
        if block["variants"] != variant:
            if block["variants"]:
                lines.append("Variant: " + " / ".join(v["label"] for v in block["variants"]))
                lines.append("")
            variant = block["variants"]
        if block["callout"] != callout:
            if block["callout"]:
                lines.extend([f"Callout: {block['callout']['title']}", ""])
            callout = block["callout"]
        anchor = block["section_anchor"]
        if anchor != section:
            source = document["url"] + ("#" + quote(anchor, safe="-_") if anchor else "")
            lines.extend([f"Section: {source}", ""])
            section = anchor
        if block["type"] == "heading":
            lines.append("#" * block["level"] + " " + block["text"])
        elif block["type"] == "code":
            longest = max((len(match) for match in re.findall(r"`+", block["text"])), default=0)
            fence = "`" * max(3, longest + 1)
            code = block["text"]
            newline = "" if code.endswith("\n") else "\n"
            lines.append(fence + (block["language"] or "") + "\n" + code + newline + fence)
        elif block["type"] == "list":
            lines.append("  " * block["depth"] + block["marker"] + " " + block["text"])
        elif block["type"] == "quote":
            lines.append("> " + block["text"])
        else:
            lines.append(block["text"])
        lines.append("")
    return "\n".join(lines)


async def capture(
    manifest_path: Path, artifact_dir: Path, client: httpx.AsyncClient, limits: FetchLimits
) -> tuple[Path, dict]:
    manifest = load_manifest(manifest_path)
    run_id = str(uuid4())
    report_path = artifact_dir / "captures" / run_id / "report.json"
    report = {
        "capture_id": run_id,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "manifest": manifest,
        "manifest_hash": json_hash(manifest),
        "parser_version": PARSER_VERSION,
        "pages": [],
    }
    write_json(report_path, report)
    for index, expected in enumerate(manifest["pages"]):
        page = {"url": expected["url"], "status": "failed", "stage": "fetch"}
        try:
            page.update(await fetch_page(client, expected["url"], artifact_dir, limits))
            page["stage"] = "parse"
            raw = (artifact_dir / page["raw_path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != page["raw_hash"]:
                raise ValueError("Raw artifact checksum mismatch")
            document = parse_page(raw, page["final_url"])
            page["stage"] = "validate"
            validate_page(document, expected)
            anchors = {
                block["section_anchor"]
                for block in document["blocks"]
                if block["type"] == "heading" and block["section_anchor"]
            }
            if any(
                block["section_anchor"] and block["section_anchor"] not in anchors
                for block in document["blocks"]
            ):
                raise ValueError("Evidence points to an unknown section anchor")
            page["stage"] = "export"
            parsed_path = f"parsed/{document['content_hash']}.json"
            markdown_path = f"parsed/{document['content_hash']}.md"
            write_json(artifact_dir / parsed_path, document)
            write_bytes(artifact_dir / markdown_path, render_markdown(document).encode("utf-8"))
            page.update(
                {
                    "status": "succeeded",
                    "stage": "complete",
                    "title": document["title"],
                    "content_hash": document["content_hash"],
                    "parsed_path": parsed_path,
                    "markdown_path": markdown_path,
                    "blocks": len(document["blocks"]),
                    "sections": sum(block["type"] == "heading" for block in document["blocks"]),
                    "code_blocks": sum(block["type"] == "code" for block in document["blocks"]),
                }
            )
        except (ValueError, OSError, httpx.HTTPError) as error:
            page["error"] = f"{type(error).__name__}: {error}"
        report["pages"].append(page)
        write_json(report_path, report)
        if index < len(manifest["pages"]) - 1:
            await asyncio.sleep(limits.pause)
    succeeded = sum(page["status"] == "succeeded" for page in report["pages"])
    report.update(
        {
            "status": "succeeded" if succeeded == len(manifest["pages"]) else "failed",
            "finished_at": datetime.now(UTC).isoformat(),
            "pages_succeeded": succeeded,
            "pages_failed": len(manifest["pages"]) - succeeded,
        }
    )
    write_json(report_path, report)
    return report_path, report
