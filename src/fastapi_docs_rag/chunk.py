"""Deterministic, source-traceable passages bounded by the real MiniLM tokenizer."""

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files

from tokenizers import Tokenizer

from fastapi_docs_rag.manifest import json_hash

CHUNKER_VERSION = "1"


@dataclass(frozen=True)
class ChunkConfig:
    body_tokens: int = 180
    overlap_tokens: int = 30
    max_input_tokens: int = 256
    prefix_tokens: int = 64

    def __post_init__(self):
        if any(type(value) is not int for value in asdict(self).values()):
            raise ValueError("Chunk settings must be integers")
        if not 16 <= self.max_input_tokens <= 256:
            raise ValueError("Complete MiniLM input limit must be between 16 and 256")
        if not 1 <= self.body_tokens <= self.max_input_tokens - 2:
            raise ValueError("Invalid body token budget")
        if not 0 <= self.overlap_tokens < self.body_tokens or self.prefix_tokens < 0:
            raise ValueError("Invalid overlap or prefix budget")


@lru_cache(maxsize=1)
def load_tokenizer() -> tuple[Tokenizer, dict]:
    assets = files("fastapi_docs_rag").joinpath("assets/minilm")
    provenance = json.loads(assets.joinpath("provenance.json").read_text())
    raw = assets.joinpath("tokenizer.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != provenance["files"]["tokenizer.json"]["sha256"]:
        raise ValueError("Packaged tokenizer checksum mismatch")
    tokenizer = Tokenizer.from_str(raw.decode("utf-8"))
    # The upstream saved tokenizer enables 128-token truncation and fixed padding.
    tokenizer.no_truncation()
    tokenizer.no_padding()
    identity = {"model": provenance["model"], "revision": provenance["revision"], "sha256": digest}
    return tokenizer, identity


def chunk_document(document: dict, config: ChunkConfig | None = None) -> dict:
    config = config or ChunkConfig()
    expected_hash = json_hash({k: v for k, v in document.items() if k != "content_hash"})
    if document.get("content_hash") != expected_hash:
        raise ValueError("Parsed document content hash mismatch")
    tokenizer, identity = load_tokenizer()
    profile = {"chunker_version": CHUNKER_VERSION, "tokenizer": identity, **asdict(config)}
    chunks = []
    excluded = []
    pending = []
    pending_key = None
    blocks = document["blocks"]

    def count(value, special=False):
        return len(tokenizer.encode(value, add_special_tokens=special).ids)

    def context(block):
        headings = " > ".join(block["heading_path"])
        labels = " / ".join(item["label"] for item in block["variants"])
        raw = f"{document['title']}\n{headings}\n{labels}"
        if block["callout"]:
            raw += "\n" + block["callout"]["title"]
        budget = min(config.prefix_tokens, config.max_input_tokens - 8)
        offsets = tokenizer.encode(raw, add_special_tokens=False).offsets
        if len(offsets) > budget:
            raw = raw[: offsets[budget - 1][1]] if budget else ""
        return raw.strip()

    def body(spans):
        return "\n\n".join(blocks[s["block_index"]]["text"][s["start"] : s["end"]] for s in spans)

    def fits(value, prefix):
        return (
            count(value) <= config.body_tokens
            and count(prefix + "\n\n" + value, special=True) <= config.max_input_tokens
        )

    def emit(spans):
        first = blocks[spans[0]["block_index"]]
        value = body(spans)
        prefix = context(first)
        embedding_input = prefix + "\n\n" + value
        partial = any(
            blocks[s["block_index"]]["type"] == "code"
            and (s["start"] != 0 or s["end"] != len(blocks[s["block_index"]]["text"]))
            for s in spans
        )
        key = json_hash(
            {
                "document_hash": document["content_hash"],
                "profile": profile,
                "spans": spans,
                "variants": first["variants"],
            }
        )
        chunks.append(
            {
                "chunk_key": key,
                "evidence_key": json_hash(
                    {
                        "url": document["url"],
                        "document_hash": document["content_hash"],
                        "anchor": first["section_anchor"],
                        "spans": spans,
                    }
                ),
                "text": value,
                "embedding_input": embedding_input,
                "embedding_input_hash": hashlib.sha256(embedding_input.encode()).hexdigest(),
                "body_tokens": count(value),
                "input_tokens": count(embedding_input, special=True),
                "heading_path": first["heading_path"],
                "section_anchor": first["section_anchor"],
                "variants": first["variants"],
                "callout": first["callout"],
                "source_spans": spans,
                "partial_code": partial,
            }
        )

    def split(index, prefix):
        block = blocks[index]
        value = block["text"]
        start = 0
        previous_end = 0
        while start < len(value):
            tail = value[start:]
            if fits(tail, prefix):
                end = len(value)
            else:
                offsets = tokenizer.encode(tail, add_special_tokens=False).offsets
                limit = min(config.body_tokens, len(offsets))
                while limit > 0:
                    cut = offsets[limit][0] if limit < len(offsets) else len(tail)
                    if block["type"] == "code":
                        newline = tail.rfind("\n", 0, cut)
                        if newline >= 0:
                            cut = newline + 1
                    if cut > 0 and fits(tail[:cut], prefix):
                        break
                    limit -= 1
                else:
                    raise ValueError("A source character cannot fit the configured input budget")
                end = start + cut
            if end <= previous_end:
                start = previous_end
                continue
            emit([{"block_index": index, "start": start, "end": end}])
            if end == len(value):
                break
            offsets = tokenizer.encode(value[start:end], add_special_tokens=False).offsets
            overlap = min(config.overlap_tokens, max(0, len(offsets) - 1))
            next_start = start + offsets[-overlap][0] if overlap else end
            if block["type"] == "code":
                newline = value.find("\n", next_start, end)
                if newline >= 0:
                    next_start = newline + 1
            previous_end = end
            start = max(start + 1, next_start)

    for index, block in enumerate(blocks):
        if block["type"] == "heading":
            if pending:
                emit(pending)
                pending = []
            excluded.append({"block_index": index, "reason": "heading retained in metadata"})
            continue
        key = (block["heading_path"], block["section_anchor"], block["variants"], block["callout"])
        span = {"block_index": index, "start": 0, "end": len(block["text"])}
        prefix = context(block)
        if pending and (key != pending_key or not fits(body([*pending, span]), prefix)):
            emit(pending)
            pending = []
        if fits(block["text"], prefix):
            pending.append(span)
            pending_key = key
        else:
            split(index, prefix)
    if pending:
        emit(pending)
    if not chunks:
        raise ValueError("Document has no searchable content")
    result = {
        "document_hash": document["content_hash"],
        "url": document["url"],
        "profile": profile,
        "chunks": chunks,
        "excluded_blocks": excluded,
    }
    result["chunk_set_hash"] = json_hash(result)
    return result
