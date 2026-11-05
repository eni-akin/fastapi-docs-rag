"""The reviewed source boundary for documentation captures."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ORIGIN = "https://fastapi.tiangolo.com"


def canonical_url(value: str) -> str:
    """Validate before any request; fragments identify evidence, not fetched pages."""
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Source URL must be a string without whitespace or controls")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "fastapi.tiangolo.com"
        or parsed.query
        or not parsed.path.startswith("/tutorial/")
        or not parsed.path.endswith("/")
        or not re.fullmatch(r"/tutorial/(?:[a-z0-9-]+/)*", parsed.path)
    ):
        raise ValueError(f"Source URL is outside the approved English tutorial: {value}")
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Manifest must be an object with version 1")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Manifest must contain a nonempty pages list")
    urls = []
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Each manifest page must be an object")
        page["url"] = canonical_url(page.get("url"))
        for key in ("expected_title", "expected_code"):
            if not isinstance(page.get(key), str) or not page[key].strip():
                raise ValueError(f"Each page requires nonempty {key}")
        urls.append(page["url"])
    if len(set(urls)) != len(urls) or urls != sorted(urls):
        raise ValueError("Manifest URLs must be unique and sorted")
    return manifest


def json_hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
