"""Offline selection checks plus an optional real pinned-tokenizer check."""

import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest

from fastapi_docs_rag import context
from fastapi_docs_rag.context import (
    INPUT_TOKENS,
    build_context,
    load_context_tokenizer,
    render_messages,
)

MODEL_DIR = Path(os.environ.get("RAG_CONTEXT_TOKENIZER_DIR", "data/models/qwen2.5-1.5b-tokenizer"))


@pytest.fixture
def fake_tokenizer(monkeypatch):
    class Counter:
        chat_template = "offline-test-template"

        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            assert tokenize and add_generation_prompt
            return {"input_ids": range(16 + sum(len(m["content"]) for m in messages) // 4)}

    tokenizer = Counter()
    identity = {
        "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()
    }
    monkeypatch.setattr(context, "_provenance", lambda: identity)
    monkeypatch.setattr(context, "load_context_tokenizer", lambda model_dir: (tokenizer, identity))
    return tokenizer


class SourceRows:
    def __init__(self, records):
        self.records = records

    def execute(self, statement, parameters):
        if "FROM rag_snapshots" in statement:
            self.result = {"state": "ready"}
        else:
            self.result = self.records
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def source(text, spans, *, kind="paragraph", variant=None, section="section", document_id=None):
    snapshot_id = str(uuid4())
    document_id = document_id or str(uuid4())
    chunk_id = str(uuid4())
    variants = [variant] if variant else []
    block = {
        "type": kind,
        "text": text,
        "heading_path": [section],
        "section_anchor": section,
        "variants": variants,
        "callout": None,
    }
    record = {
        "chunk_id": chunk_id,
        "snapshot_id": snapshot_id,
        "document_id": document_id,
        "document_content_hash": "a" * 64,
        "document_raw_hash": "b" * 64,
        "source_url": "https://fastapi.tiangolo.com/tutorial/testing/",
        "url": "https://fastapi.tiangolo.com/tutorial/testing/#" + section,
        "title": "Testing",
        "heading_path": [section],
        "section_anchor": section,
        "variants": variants,
        "callout": None,
        "source_spans": [{"block_index": 0, "start": start, "end": end} for start, end in spans],
        "partial_code": kind == "code" and (spans[0][0] != 0 or spans[-1][1] != len(text)),
        "document": {"content_hash": "a" * 64, "blocks": [block]},
    }
    record["text"] = "\n\n".join(text[start:end] for start, end in spans)
    row = {key: value for key, value in record.items() if key != "document"}
    return record, row


def test_pinned_tokenizer_counts_unicode_messages_once():
    if not (MODEL_DIR / "tokenizer.json").is_file():
        pytest.skip("Run prepare-context-tokenizer or set RAG_CONTEXT_TOKENIZER_DIR")
    tokenizer, identity = load_context_tokenizer(MODEL_DIR)
    messages = render_messages("How does yield clean up? 中文", [])
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    assert len(ids["input_ids"]) > 0
    assert identity["chat_template_sha256"]


def test_overlap_merges_exact_spans_and_retains_both_chunks(fake_tokenizer):
    first, row1 = source("Unicode évidence 中文 and yield cleanup", [(0, 23)])
    second, row2 = source("Unicode évidence 中文 and yield cleanup", [(17, 37)])
    second.update({key: first[key] for key in ("snapshot_id", "document_id")})
    row2.update({key: second[key] for key in ("snapshot_id", "document_id")})
    bundle = build_context(
        SourceRows([first, second]),
        first["snapshot_id"],
        "yield?",
        [row1, row2],
        model_dir=MODEL_DIR,
    )
    assert len(bundle["entries"]) == 1
    entry = bundle["entries"][0]
    assert entry["text"] == "Unicode évidence 中文 and yield cleanup"
    assert entry["chunk_ids"] == [first["chunk_id"], second["chunk_id"]]
    assert entry["source_spans"] == [{"block_index": 0, "start": 0, "end": 37}]
    assert bundle["evidence_lookup"]["E1"]["chunk_ids"] == entry["chunk_ids"]
    assert bundle["profile"]["max_input_tokens"] == INPUT_TOKENS
    assert bundle["profile"]["renderer_sha256"]
    assert bundle["profile"]["selection_version"]
    assert bundle["prompt_tokens"] == len(
        fake_tokenizer.apply_chat_template(
            bundle["messages"], tokenize=True, add_generation_prompt=True
        )["input_ids"]
    )


def test_variant_conflict_and_budget_skip(fake_tokenizer):
    text = "def f():\n    yield 'évidence'\n"
    first, row1 = source(
        text,
        [(0, len(text))],
        kind="code",
        variant={"group": "g", "index": 0, "label": "Python 3.10+"},
    )
    second, row2 = source(
        text,
        [(0, len(text))],
        kind="code",
        variant={"group": "g", "index": 1, "label": "Python 3.8+"},
        document_id=first["document_id"],
    )
    second["snapshot_id"] = row2["snapshot_id"] = first["snapshot_id"]
    bundle = build_context(
        SourceRows([first, second]),
        first["snapshot_id"],
        "yield?",
        [row1, row2],
        model_dir=MODEL_DIR,
    )
    assert len(bundle["entries"]) == 2
    assert bundle["entries"][0]["variants"] != bundle["entries"][1]["variants"]
    tight = build_context(
        SourceRows([first, second]),
        first["snapshot_id"],
        "yield?",
        [row1, row2],
        model_dir=MODEL_DIR,
        max_input_tokens=bundle["prompt_tokens"] - 1,
    )
    assert len(tight["entries"]) == 1
    assert tight["skipped"][0]["reason"] == "complete prompt token budget"


def test_partial_code_expands_only_when_complete_prompt_fits(fake_tokenizer):
    text = "def f():\n" + "    yield resource\n" * 30
    record, row = source(text, [(0, 25)], kind="code")
    bundle = build_context(
        SourceRows([record]), record["snapshot_id"], "code?", [row], model_dir=MODEL_DIR
    )
    assert bundle["entries"][0]["text"] == text
    assert bundle["entries"][0]["expanded_code_blocks"] == [0]
    assert not bundle["entries"][0]["partial_code"]
    small = build_context(
        SourceRows([record]),
        record["snapshot_id"],
        "code?",
        [row],
        model_dir=MODEL_DIR,
        max_input_tokens=bundle["prompt_tokens"] - 1,
    )
    assert small["entries"][0]["partial_code"]
    assert small["entries"][0]["expanded_code_blocks"] == []


def test_empty_context_and_source_mismatch(fake_tokenizer):
    record, row = source("yield resource", [(0, 14)])
    empty = build_context(
        SourceRows([]), record["snapshot_id"], "unknown?", [], model_dir=MODEL_DIR
    )
    assert empty["entries"] == [] and empty["prompt_tokens"] <= INPUT_TOKENS
    with pytest.raises(ValueError, match="mismatched text"):
        build_context(
            SourceRows([record]),
            record["snapshot_id"],
            "yield?",
            [{**row, "text": "invented"}],
            model_dir=MODEL_DIR,
        )
    with pytest.raises(ValueError, match="absent"):
        build_context(SourceRows([]), record["snapshot_id"], "yield?", [row], model_dir=MODEL_DIR)
    with pytest.raises(ValueError, match="mismatched snapshot_id"):
        build_context(
            SourceRows([record]),
            record["snapshot_id"],
            "yield?",
            [{**row, "snapshot_id": str(uuid4())}],
            model_dir=MODEL_DIR,
        )
    with pytest.raises(ValueError, match="mismatched variants"):
        build_context(
            SourceRows([record]),
            record["snapshot_id"],
            "yield?",
            [{**row, "variants": [{"label": "invented"}]}],
            model_dir=MODEL_DIR,
        )
    with pytest.raises(ValueError, match="Question and instructions exceed"):
        build_context(
            SourceRows([]),
            record["snapshot_id"],
            "yield?",
            [],
            model_dir=MODEL_DIR,
            max_input_tokens=10,
        )


def test_adjacent_blocks_merge_without_losing_source_order(fake_tokenizer):
    first, row1 = source("first paragraph", [(0, 15)])
    second = dict(first)
    second["chunk_id"] = str(uuid4())
    second["source_spans"] = [{"block_index": 1, "start": 0, "end": 16}]
    second["text"] = "second paragraph"
    block = dict(first["document"]["blocks"][0])
    second["document"] = {
        "content_hash": first["document_content_hash"],
        "blocks": [first["document"]["blocks"][0], {**block, "text": "second paragraph"}],
    }
    first["document"] = second["document"]
    row2 = {key: value for key, value in second.items() if key != "document"}
    bundle = build_context(
        SourceRows([first, second]),
        first["snapshot_id"],
        "summarize",
        [row1, row2],
        model_dir=MODEL_DIR,
    )
    assert len(bundle["entries"]) == 1
    assert bundle["entries"][0]["text"] == "first paragraph\n\nsecond paragraph"
    assert bundle["entries"][0]["source_spans"] == [
        {"block_index": 0, "start": 0, "end": 15},
        {"block_index": 1, "start": 0, "end": 16},
    ]


def test_middle_span_containment_is_not_a_second_entry(fake_tokenizer):
    first, row1 = source("first", [(0, 5)])
    block = first["document"]["blocks"][0]
    blocks = [block, {**block, "text": "middle"}, {**block, "text": "last"}]
    first["document"] = {"content_hash": first["document_content_hash"], "blocks": blocks}
    first["source_spans"] = [
        {"block_index": i, "start": 0, "end": len(b["text"])} for i, b in enumerate(blocks)
    ]
    first["text"] = "first\n\nmiddle\n\nlast"
    row1.update({"source_spans": first["source_spans"], "text": first["text"]})
    second = {
        **first,
        "chunk_id": str(uuid4()),
        "source_spans": [{"block_index": 1, "start": 1, "end": 5}],
        "text": "iddl",
    }
    row2 = {key: value for key, value in second.items() if key != "document"}
    bundle = build_context(
        SourceRows([first, second]), first["snapshot_id"], "middle?", [row1, row2]
    )
    assert len(bundle["entries"]) == 1
    assert bundle["entries"][0]["text"] == first["text"]
    assert bundle["entries"][0]["chunk_ids"] == [first["chunk_id"], second["chunk_id"]]


def test_bridge_span_coalesces_every_connected_entry(fake_tokenizer):
    text = "abcdefghijklmnopqrstuvwxyz0123456789"
    first, row1 = source(text, [(0, 10)])
    second, row2 = source(text, [(20, 30)], document_id=first["document_id"])
    bridge, row3 = source(text, [(8, 22)], document_id=first["document_id"])
    for record, row in ((second, row2), (bridge, row3)):
        record["snapshot_id"] = row["snapshot_id"] = first["snapshot_id"]
    bundle = build_context(
        SourceRows([first, second, bridge]),
        first["snapshot_id"],
        "which range?",
        [row1, row2, row3],
    )
    assert len(bundle["entries"]) == 1
    entry = bundle["entries"][0]
    assert entry["source_spans"] == [{"block_index": 0, "start": 0, "end": 30}]
    assert entry["text"] == text[:30]
    assert entry["chunk_ids"] == [first["chunk_id"], second["chunk_id"], bridge["chunk_id"]]


def test_disjoint_code_fragments_expand_to_one_full_source(fake_tokenizer):
    text = "def f():\n" + "    yield resource\n" * 30
    first, row1 = source(text, [(0, 25)], kind="code")
    second = {
        **first,
        "chunk_id": str(uuid4()),
        "source_spans": [{"block_index": 0, "start": 50, "end": 75}],
        "text": text[50:75],
    }
    row2 = {key: value for key, value in second.items() if key != "document"}
    bundle = build_context(SourceRows([first, second]), first["snapshot_id"], "code?", [row1, row2])
    assert len(bundle["entries"]) == 1
    assert bundle["entries"][0]["text"] == text
    assert bundle["entries"][0]["source_spans"] == [
        {"block_index": 0, "start": 0, "end": len(text)}
    ]
    assert bundle["entries"][0]["chunk_ids"] == [first["chunk_id"], second["chunk_id"]]
    assert bundle["entries"][0]["expanded_code_blocks"] == [0]
    assert bundle["evidence_lookup"]["E1"]["chunk_ids"] == bundle["entries"][0]["chunk_ids"]


def test_real_snapshot_bundle(database, capture_factory, fake_tokenizer):
    from fastapi_docs_rag.db import import_capture, migrate
    from fastapi_docs_rag.retrieve import search

    migrate(database)
    report, root = capture_factory()
    snapshot = import_capture(database, report, root)["snapshot_id"]
    rows = search(database, snapshot, "FastAPI", limit=5)
    bundle = build_context(database, snapshot, "How do I define an app?", rows, model_dir=MODEL_DIR)
    assert bundle["entries"]
    assert bundle["prompt_tokens"] <= INPUT_TOKENS
    assert all(entry["snapshot_id"] == snapshot for entry in bundle["entries"])


def test_context_cli_prints_and_exports_bundle(monkeypatch, capsys):
    from fastapi_docs_rag import cli

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    seen = []
    monkeypatch.setattr(cli, "connect_database", Connection)
    monkeypatch.setattr(
        cli,
        "search",
        lambda connection, snapshot, query, limit, mode, **kwargs: (
            seen.append((snapshot, query, limit, mode)) or [{"chunk_id": "candidate"}]
        ),
    )
    monkeypatch.setattr(context, "load_context_tokenizer", lambda directory: (object(), {}))
    bundle = {
        "version": "grounded-evidence-v1",
        "messages": [{"content": "Grounded instructions"}],
        "question": "question",
        "entries": [
            {
                "evidence_id": "E1",
                "title": "Testing",
                "url": "https://example.test/#a",
                "document_id": "doc",
                "document_content_hash": "hash",
                "document_raw_hash": "raw",
                "chunk_ids": ["candidate"],
                "source_spans": [{"block_index": 1, "start": 0, "end": 4}],
                "variants": [],
                "partial_code": False,
                "expanded_code_blocks": [],
                "text": "text",
            }
        ],
        "prompt_tokens": 300,
        "profile": {"max_input_tokens": INPUT_TOKENS},
        "snapshot_id": "snapshot",
        "skipped": [],
        "sufficiency_policy": "unvalidated",
    }
    monkeypatch.setattr(context, "build_context", lambda *args, **kwargs: bundle)
    for output_json in (False, True):
        monkeypatch.setattr(
            "sys.argv",
            ["rag", "context", "--snapshot", "snapshot", "--query", "question"]
            + (["--json"] if output_json else []),
        )
        assert cli.main() == 0
        output = capsys.readouterr().out
        assert '"prompt_tokens": 300' in output if output_json else "E1. Testing" in output
        if not output_json:
            assert "Question: question" in output
    assert seen == [("snapshot", "question", 20, "hybrid-rerank")] * 2


def test_prepare_context_tokenizer_cli_is_explicit(monkeypatch, capsys):
    from fastapi_docs_rag import cli

    seen = []
    monkeypatch.setattr(
        context, "prepare_context_tokenizer", lambda path: seen.append(path) or {"model": "pinned"}
    )
    monkeypatch.setattr("sys.argv", ["rag", "prepare-context-tokenizer", "--model-dir", "model"])
    assert cli.main() == 0
    assert seen == [Path("model")]
    assert '"model": "pinned"' in capsys.readouterr().out
