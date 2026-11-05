import json
from pathlib import Path

import pytest

from fastapi_docs_rag.manifest import canonical_url, json_hash, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_seed_manifest():
    manifest = load_manifest(ROOT / "corpus/manifests/tutorial-seed.json")
    assert len(manifest["pages"]) == 8
    assert json_hash(manifest) == json_hash(json.loads(json.dumps(manifest)))


@pytest.mark.parametrize(
    "url",
    [
        "http://fastapi.tiangolo.com/tutorial/testing/",
        "https://evil.example/tutorial/testing/",
        "https://fastapi.tiangolo.com.evil.example/tutorial/testing/",
        "https://user@fastapi.tiangolo.com/tutorial/testing/",
        "https://fastapi.tiangolo.com:443/tutorial/testing/",
        "https://fastapi.tiangolo.com/es/tutorial/testing/",
        "https://fastapi.tiangolo.com/advanced/",
        "https://fastapi.tiangolo.com/tutorial/../advanced/",
        "https://fastapi.tiangolo.com/tutorial/%2e%2e/advanced/",
        "https://fastapi.tiangolo.com/tutorial/testing/?x=1",
        "https://fastapi.tiangolo.com/tutorial/te\nsting/",
        None,
    ],
)
def test_reject_unapproved_url(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_strip_fragment():
    assert canonical_url("https://fastapi.tiangolo.com/tutorial/testing/#using-testclient") == (
        "https://fastapi.tiangolo.com/tutorial/testing/"
    )


@pytest.mark.parametrize(
    "pages", [[], [{"url": "https://fastapi.tiangolo.com/tutorial/"}], ["not an object"]]
)
def test_invalid_manifest(tmp_path, pages):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 1, "pages": pages}))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_duplicate_canonical_pages(tmp_path):
    page = {
        "url": "https://fastapi.tiangolo.com/tutorial/testing/",
        "expected_title": "Testing",
        "expected_code": "TestClient",
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 1, "pages": [page, page | {"url": page["url"] + "#x"}]}))
    with pytest.raises(ValueError, match="unique"):
        load_manifest(path)
