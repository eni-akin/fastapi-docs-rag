import asyncio
import gzip
import hashlib

import httpx
import pytest

from fastapi_docs_rag.fetch import FetchError, FetchLimits, fetch_page

URL = "https://fastapi.tiangolo.com/tutorial/testing/"


def run_fetch(tmp_path, handler, limits=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_page(client, URL, tmp_path, limits or FetchLimits())

    return asyncio.run(run())


def html_response(body=b"<article>Test</article>", **kwargs):
    return httpx.Response(200, content=body, headers={"content-type": "text/html"}, **kwargs)


def test_content_addressed_capture_and_reuse(tmp_path):
    body = b"<article>Test</article>"
    first = run_fetch(tmp_path, lambda request: html_response(body))
    second = run_fetch(tmp_path, lambda request: html_response(body))
    assert first["raw_hash"] == hashlib.sha256(body).hexdigest()
    assert first["raw_path"] == second["raw_path"]
    assert (tmp_path / first["raw_path"]).read_bytes() == body
    assert len(list((tmp_path / "raw").glob("*.html"))) == 1


def test_external_redirect_not_requested(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example/"})

    with pytest.raises(ValueError, match="approved"):
        run_fetch(tmp_path, handler)
    assert calls == [URL]


def test_valid_redirect_and_final_url(tmp_path):
    target = "https://fastapi.tiangolo.com/tutorial/request-body/"

    def handler(request):
        if str(request.url) == URL:
            return httpx.Response(302, headers={"location": "../request-body/"})
        return html_response()

    result = run_fetch(tmp_path, handler)
    assert result["url"] == URL
    assert result["final_url"] == target


def test_compressed_body_rejected_before_stream_decompression(tmp_path):
    consumed = []

    class CompressedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            consumed.append(True)
            yield gzip.compress(b"x" * 10_485_760)

    def handler(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(
            200,
            stream=CompressedStream(),
            headers={"content-type": "text/html", "content-encoding": "gzip"},
        )

    with pytest.raises(FetchError, match="encoding"):
        run_fetch(tmp_path, handler, FetchLimits(max_bytes=100))
    assert consumed == []
    assert not list(tmp_path.rglob("*.html"))


def test_streaming_body_size_limit(tmp_path):
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 60
            yield b"x" * 60

    with pytest.raises(FetchError, match="decompressed"):
        run_fetch(
            tmp_path,
            lambda request: httpx.Response(
                200, stream=Stream(), headers={"content-type": "text/html"}
            ),
            FetchLimits(max_bytes=100),
        )
    assert not list(tmp_path.rglob("*.html"))


@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(200, content=b"{}", headers={"content-type": "application/json"}), "HTML"),
        (httpx.Response(404), "HTTP 404"),
        (httpx.Response(200, headers={"content-type": "text/html"}), "Empty"),
        (httpx.Response(302, headers={"location": URL}), "redirect"),
    ],
)
def test_permanent_failures(tmp_path, response, message):
    with pytest.raises(FetchError, match=message):
        run_fetch(tmp_path, lambda request: response)


def test_retry_after_then_success(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return html_response()

    assert run_fetch(tmp_path, handler)["attempts"] == 2
    assert len(calls) == 2


def test_deadline_rejects_long_retry_after(tmp_path):
    with pytest.raises(FetchError, match="deadline"):
        run_fetch(tmp_path, lambda request: httpx.Response(503, headers={"retry-after": "1000"}))


def test_total_request_deadline(tmp_path):
    async def handler(request):
        await asyncio.sleep(0.03)
        return html_response()

    with pytest.raises(FetchError, match="TimeoutError"):
        run_fetch(tmp_path, handler, FetchLimits(request_timeout=0.01, attempts=1))


def test_corrupt_existing_artifact(tmp_path):
    body = b"<article>Test</article>"
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / f"{hashlib.sha256(body).hexdigest()}.html").write_bytes(b"corrupt")
    with pytest.raises(FetchError, match="corrupt"):
        run_fetch(tmp_path, lambda request: html_response(body))


@pytest.mark.parametrize(
    "kwargs", [{"attempts": 0}, {"max_bytes": -1}, {"pause": -1}, {"page_deadline": float("nan")}]
)
def test_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        FetchLimits(**kwargs)
