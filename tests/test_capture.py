import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from fastapi_docs_rag import cli, ingest
from fastapi_docs_rag.fetch import FetchLimits
from fastapi_docs_rag.ingest import capture, render_markdown
from fastapi_docs_rag.manifest import json_hash
from fastapi_docs_rag.parse import parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def run_capture(tmp_path, responses):
    pages = [
        {
            "url": f"https://fastapi.tiangolo.com/tutorial/{name}/",
            "expected_title": title,
            "expected_code": code,
        }
        for name, title, code in [
            ("first-steps", "First Steps", "FastAPI"),
            ("testing", "Testing", "TestClient"),
        ]
    ]
    manifest = tmp_path / "seed.json"
    manifest.write_text(json.dumps({"version": 1, "pages": pages}))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: responses[request.url.path])
        ) as client:
            return await capture(manifest, tmp_path / "artifacts", client, FetchLimits(pause=0))

    return asyncio.run(run())


def valid_responses():
    return {
        "/tutorial/first-steps/": httpx.Response(
            200,
            content=(FIXTURES / "first-steps.html").read_bytes(),
            headers={"content-type": "text/html"},
        ),
        "/tutorial/testing/": httpx.Response(
            200,
            text=(
                '<article class="md-content__inner"><h1 id="testing">Testing</h1>'
                "<p>Use the test client.</p><pre><code>client = TestClient(app)\n"
                "</code></pre></article>"
            ),
            headers={"content-type": "text/html"},
        ),
    }


def test_capture_report_and_exports(tmp_path):
    path, report = run_capture(tmp_path, valid_responses())
    assert json.loads(path.read_text()) == report
    assert report["status"] == "succeeded"
    assert report["pages_succeeded"] == 2
    assert report["manifest_hash"] == json_hash(report["manifest"])
    root = tmp_path / "artifacts"
    for page in report["pages"]:
        raw = (root / page["raw_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == page["raw_hash"]
        document = json.loads((root / page["parsed_path"]).read_text())
        assert parse_page(raw, page["final_url"]) == document
        assert document["content_hash"] == page["content_hash"]
        assert document["content_hash"] == json_hash(
            {key: value for key, value in document.items() if key != "content_hash"}
        )
        markdown = (root / page["markdown_path"]).read_text()
        assert document["url"] in markdown
        assert page["code_blocks"] >= 1


def test_failed_page_preserves_successes_and_raw_parse_failure(tmp_path):
    responses = valid_responses()
    responses["/tutorial/first-steps/"] = httpx.Response(404)
    responses["/tutorial/testing/"] = httpx.Response(
        200, text="<nav>Changed layout</nav>", headers={"content-type": "text/html"}
    )
    path, report = run_capture(tmp_path, responses)
    assert report["status"] == "failed"
    assert report["pages_failed"] == 2
    assert report["pages"][0]["stage"] == "fetch"
    assert "404" in report["pages"][0]["error"]
    assert report["pages"][1]["stage"] == "parse"
    assert (tmp_path / "artifacts" / report["pages"][1]["raw_path"]).exists()
    assert json.loads(path.read_text())["status"] == "failed"


def test_mixed_success_is_not_a_successful_capture(tmp_path):
    responses = valid_responses()
    responses["/tutorial/testing/"] = httpx.Response(404)
    _, report = run_capture(tmp_path, responses)
    assert report["status"] == "failed"
    assert report["pages_succeeded"] == 1
    assert report["pages_failed"] == 1
    assert report["pages"][0]["parsed_path"]


def test_markdown_keeps_code_fences_and_variant_labels():
    html = (FIXTURES / "structure.html").read_bytes().replace(b"return None", b"return '```'")
    document = parse_page(html, "https://fastapi.tiangolo.com/tutorial/testing/")
    markdown = render_markdown(document)
    assert "Variant: Python 3.10+ Annotated" in markdown
    assert "Variant: Python 3.9+ legacy" in markdown
    assert "````python\ndef legacy():\n    return '```'\n````" in markdown
    assert "#warning" in markdown


def test_validation_failure_preserves_raw_evidence(tmp_path):
    responses = valid_responses()
    responses["/tutorial/testing/"] = httpx.Response(
        200,
        text='<article class="md-content__inner"><h1>Testing</h1>'
        "<p>Example changed.</p><pre><code>WrongClient(app)</code></pre></article>",
        headers={"content-type": "text/html"},
    )
    _, report = run_capture(tmp_path, responses)
    page = report["pages"][1]
    assert report["status"] == "failed"
    assert page["stage"] == "validate"
    assert "Expected code" in page["error"]
    assert (tmp_path / "artifacts" / page["raw_path"]).exists()


def test_markdown_write_failure_is_reported(tmp_path, monkeypatch):
    def failed_export(path, content):
        raise OSError("disk full")

    monkeypatch.setattr(ingest, "write_bytes", failed_export)
    path, report = run_capture(tmp_path, valid_responses())
    assert report["status"] == "failed"
    assert all(page["stage"] == "export" for page in report["pages"])
    assert all("disk full" in page["error"] for page in report["pages"])
    assert json.loads(path.read_text())["pages_failed"] == 2


@pytest.mark.parametrize("status, exit_code", [("succeeded", 0), ("failed", 1)])
def test_cli_exit_codes_and_diagnostics(status, exit_code, tmp_path, monkeypatch, capsys):
    async def fake_capture(manifest, output, client, limits):
        assert output == tmp_path
        pages = (
            []
            if status == "succeeded"
            else [
                {
                    "url": "https://fastapi.tiangolo.com/tutorial/testing/",
                    "stage": "validate",
                    "status": "failed",
                    "error": "expected example missing",
                }
            ]
        )
        return tmp_path / "report.json", {
            "status": status,
            "pages_succeeded": int(status == "succeeded"),
            "pages_failed": int(status == "failed"),
            "pages": pages,
        }

    monkeypatch.setattr(cli, "capture", fake_capture)
    monkeypatch.setattr("sys.argv", ["rag", "capture", "--output", str(tmp_path)])
    assert cli.main() == exit_code
    output = capsys.readouterr()
    assert f"{status}:" in output.out
    assert "Report:" in output.out
    if status == "failed":
        assert "[validate]: expected example missing" in output.err
