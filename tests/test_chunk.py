from pathlib import Path

import pytest

from fastapi_docs_rag.chunk import ChunkConfig, chunk_document, load_tokenizer
from fastapi_docs_rag.manifest import json_hash
from fastapi_docs_rag.parse import parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def document_with(text, kind="paragraph", heading="Example"):
    block = {
        "type": kind,
        "text": text,
        "heading_path": [heading],
        "section_anchor": "example",
        "variants": [],
        "callout": None,
    }
    document = {
        "url": "https://fastapi.tiangolo.com/tutorial/testing/",
        "title": heading,
        "parser_version": "test",
        "blocks": [block],
    }
    document["content_hash"] = json_hash(document)
    return document


def assert_integrity(document, result):
    tokenizer, _ = load_tokenizer()
    coverage = {
        index: set() for index, b in enumerate(document["blocks"]) if b["type"] != "heading"
    }
    for chunk in result["chunks"]:
        assert chunk["input_tokens"] == len(tokenizer.encode(chunk["embedding_input"]).ids)
        assert chunk["input_tokens"] <= result["profile"]["max_input_tokens"]
        parts = []
        for span in chunk["source_spans"]:
            index, start, end = span["block_index"], span["start"], span["end"]
            parts.append(document["blocks"][index]["text"][start:end])
            coverage[index].update(range(start, end))
            assert document["blocks"][index]["variants"] == chunk["variants"]
        assert chunk["text"] == "\n\n".join(parts)
    for index, positions in coverage.items():
        assert positions == set(range(len(document["blocks"][index]["text"])))


def test_upstream_truncation_and_padding_are_disabled():
    tokenizer, _ = load_tokenizer()
    assert tokenizer.truncation is None and tokenizer.padding is None
    assert len(tokenizer.encode("word " * 300).ids) == 302


@pytest.mark.parametrize("fixture", ["structure", "first-steps", "dependencies", "yield"])
def test_fixture_chunks_are_deterministic_and_traceable(fixture):
    document = parse_page(
        (FIXTURES / f"{fixture}.html").read_bytes(),
        "https://fastapi.tiangolo.com/tutorial/testing/",
    )
    result = chunk_document(document)
    assert result == chunk_document(document)
    assert_integrity(document, result)
    assert len({c["chunk_key"] for c in result["chunks"]}) == len(result["chunks"])
    assert len(result["excluded_blocks"]) == sum(b["type"] == "heading" for b in document["blocks"])


@pytest.mark.parametrize(
    "text, kind",
    [
        ("A paragraph with Unicode évidence 中文 and indentation.\n" * 100, "paragraph"),
        ("def example():\n" + "    yield resource\n" * 300, "code"),
        ("    " + "value + " * 400 + "result\n", "code"),
    ],
)
def test_oversized_content_preserved(text, kind):
    document = document_with(text, kind)
    result = chunk_document(document)
    assert len(result["chunks"]) > 1
    assert_integrity(document, result)
    if kind == "code":
        assert all(chunk["partial_code"] for chunk in result["chunks"])


def test_code_prefers_line_boundaries():
    document = document_with("    yield resource\n" * 300, "code")
    result = chunk_document(document)
    for chunk in result["chunks"]:
        span = chunk["source_spans"][0]
        assert document["blocks"][0]["text"][span["start"] : span["end"]].endswith("\n")
        assert span["start"] == 0 or document["blocks"][0]["text"][span["start"] - 1] == "\n"


def test_short_code_stays_whole_with_nearby_prose():
    document = document_with("Use a dependency to provide a resource.")
    document["blocks"].append(document["blocks"][0] | {"type": "code", "text": "yield resource\n"})
    document["content_hash"] = json_hash({k: v for k, v in document.items() if k != "content_hash"})
    result = chunk_document(document)
    assert len(result["chunks"]) == 1
    assert len(result["chunks"][0]["source_spans"]) == 2
    assert not result["chunks"][0]["partial_code"]


def test_long_heading_is_metadata_not_silent_body_truncation():
    document = document_with("yield resource " * 150, heading="long heading " * 400)
    result = chunk_document(document)
    assert all(c["heading_path"] == document["blocks"][0]["heading_path"] for c in result["chunks"])
    assert_integrity(document, result)


def test_profile_change_changes_chunk_identity_and_overlap():
    document = document_with(" ".join(f"word{i}" for i in range(300)))
    first = chunk_document(document)
    second = chunk_document(document, ChunkConfig(overlap_tokens=0))
    assert first["chunk_set_hash"] != second["chunk_set_hash"]
    assert first["chunks"][0]["chunk_key"] != second["chunks"][0]["chunk_key"]
    assert (
        first["chunks"][1]["source_spans"][0]["start"]
        < first["chunks"][0]["source_spans"][0]["end"]
    )
    assert_integrity(document, second)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"body_tokens": 0},
        {"overlap_tokens": 180},
        {"max_input_tokens": 257},
        {"prefix_tokens": -1},
        {"body_tokens": True},
    ],
)
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        ChunkConfig(**kwargs)


def test_modified_document_is_rejected():
    document = document_with("A short passage")
    document["blocks"][0]["text"] = "Changed"
    with pytest.raises(ValueError, match="hash"):
        chunk_document(document)
