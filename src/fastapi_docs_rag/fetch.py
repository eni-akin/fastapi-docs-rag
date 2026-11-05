"""Sequential, bounded acquisition of approved rendered HTML."""

import asyncio
import hashlib
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx

from fastapi_docs_rag.artifacts import write_bytes
from fastapi_docs_rag.manifest import canonical_url

REDIRECTS = {301, 302, 303, 307, 308}
TRANSIENT = {429, 500, 502, 503, 504}


class FetchError(ValueError):
    """A required page could not be captured safely."""


@dataclass(frozen=True)
class FetchLimits:
    max_bytes: int = 5 * 1024 * 1024
    request_timeout: float = 20
    page_deadline: float = 90
    attempts: int = 3
    max_redirects: int = 3
    pause: float = 0.25

    def __post_init__(self):
        for name in ("max_bytes", "attempts", "max_redirects"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "max_redirects" else 1):
                raise ValueError(f"Invalid {name}")
        for name in ("request_timeout", "page_deadline", "pause"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0 or (name != "pause" and value == 0):
                raise ValueError(f"Invalid {name}")


def retry_delay(header: str | None, attempt: int) -> float:
    if header:
        try:
            seconds = float(header)
            if math.isfinite(seconds) and seconds >= 0:
                return seconds
        except ValueError:
            try:
                date = parsedate_to_datetime(header)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=UTC)
                return max(0, (date - datetime.now(UTC)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return float(2 ** (attempt - 1))


async def _download(client: httpx.AsyncClient, url: str, limits: FetchLimits):
    for redirect in range(limits.max_redirects + 1):
        async with client.stream(
            "GET", url, follow_redirects=False, headers={"accept-encoding": "identity"}
        ) as response:
            if response.status_code in REDIRECTS:
                location = response.headers.get("location")
                if not location or redirect == limits.max_redirects:
                    raise FetchError("Missing redirect location or too many redirects")
                url = canonical_url(urljoin(url, location))
                continue
            response.raise_for_status()
            if response.headers.get("content-encoding", "identity").strip().lower() != "identity":
                raise FetchError("Unexpected content encoding; capture requires identity encoding")
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type not in {"text/html", "application/xhtml+xml"}:
                raise FetchError(f"Expected HTML, got {media_type or 'missing content type'}")
            content = bytearray()
            async for part in response.aiter_bytes():
                if len(content) + len(part) > limits.max_bytes:
                    raise FetchError(f"HTML exceeds {limits.max_bytes} decompressed bytes")
                content.extend(part)
            if not content:
                raise FetchError("Empty HTML response")
            return bytes(content), url, response.headers
    raise FetchError("Redirect limit exceeded")


async def fetch_page(
    client: httpx.AsyncClient, url: str, artifact_dir: Path, limits: FetchLimits
) -> dict:
    url = canonical_url(url)
    deadline = time.monotonic() + limits.page_deadline
    for attempt in range(1, limits.attempts + 1):
        delay = float(2 ** (attempt - 1))
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError("Page deadline exceeded")
            async with asyncio.timeout(min(limits.request_timeout, remaining)):
                content, final_url, headers = await _download(client, url, limits)
            digest = hashlib.sha256(content).hexdigest()
            relative = f"raw/{digest}.html"
            path = artifact_dir / relative
            if path.exists():
                if path.read_bytes() != content:
                    raise FetchError(f"Existing raw artifact is corrupt: {relative}")
            else:
                write_bytes(path, content)
            return {
                "url": url,
                "final_url": final_url,
                "fetched_at": datetime.now(UTC).isoformat(),
                "raw_hash": digest,
                "raw_path": relative,
                "bytes": len(content),
                "content_type": headers.get("content-type"),
                "etag": headers.get("etag"),
                "last_modified": headers.get("last-modified"),
                "attempts": attempt,
            }
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in TRANSIENT:
                raise FetchError(f"HTTP {error.response.status_code} for {url}") from error
            delay = retry_delay(error.response.headers.get("retry-after"), attempt)
            reason = f"HTTP {error.response.status_code}"
        except (httpx.RequestError, TimeoutError) as error:
            reason = type(error).__name__
        if attempt == limits.attempts:
            raise FetchError(f"Capture failed after {attempt} attempts: {reason}")
        if delay >= deadline - time.monotonic():
            raise FetchError(f"Retry delay exceeds page deadline: {reason}")
        await asyncio.sleep(delay)
    raise FetchError("Capture attempts exhausted")
