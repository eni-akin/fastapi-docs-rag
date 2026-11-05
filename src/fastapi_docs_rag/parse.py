"""Extract ordered evidence blocks from FastAPI's rendered documentation."""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from fastapi_docs_rag.manifest import canonical_url, json_hash

PARSER_VERSION = "1"
HEADINGS = {f"h{level}" for level in range(1, 7)}


def text(node: Tag) -> str:
    return re.sub(r"\s+", " ", node.get_text()).strip()


def parse_page(html: bytes, url: str) -> dict:
    url = canonical_url(url)
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.md-content__inner")
    if article is None:
        raise ValueError("Missing FastAPI article.md-content__inner; inspect the captured layout")
    for node in article.select("script, style, nav, button, a.headerlink, .md-content__button"):
        node.decompose()
    title = article.find("h1")
    if title is None or not text(title):
        raise ValueError("Missing article title")
    blocks = []
    heading_stack = []
    tab_counter = 0

    def emit(kind, value, variants, callout, **extra):
        if not value.strip():
            return
        blocks.append(
            {
                "type": kind,
                "text": value,
                "heading_path": [item[1] for item in heading_stack],
                "section_anchor": heading_stack[-1][2] if heading_stack else None,
                "variants": list(variants),
                "callout": callout,
                **extra,
            }
        )

    def walk(node, variants=(), callout=None, list_depth=0):
        nonlocal tab_counter
        if not isinstance(node, Tag):
            return
        classes = node.get("class", [])
        if node.name in HEADINGS:
            level = int(node.name[1])
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text(node), node.get("id")))
            emit("heading", text(node), variants, callout, level=level)
        elif "tabbed-set" in classes:
            tab_counter += 1
            group = f"tabs-{tab_counter}"
            labels_node = node.find(class_="tabbed-labels", recursive=False)
            content = node.find(class_="tabbed-content", recursive=False)
            labels = labels_node.find_all("label", recursive=False) if labels_node else []
            panels = content.find_all(class_="tabbed-block", recursive=False) if content else []
            if not labels or len(labels) != len(panels):
                raise ValueError("Unrecognized code-tab layout or missing labeled panels")
            shared_headings = list(heading_stack)
            for index, (label, panel) in enumerate(zip(labels, panels, strict=True)):
                heading_stack[:] = shared_headings
                if not text(label):
                    raise ValueError("Empty code-tab label")
                variant = {"group": group, "index": index, "label": text(label)}
                walk(panel, (*variants, variant), callout, list_depth)
            heading_stack[:] = shared_headings
        elif "admonition" in classes or node.name == "details":
            title_node = node.find(["summary", "p"], class_="admonition-title", recursive=False)
            if title_node is None:
                title_node = node.find("summary", recursive=False)
            title_text = text(title_node) if title_node else "Note"
            info = {
                "title": title_text,
                "kind": next((item for item in classes if item != "admonition"), "note"),
            }
            emit("callout", title_text, variants, info)
            for child in node.children:
                if child is not title_node:
                    walk(child, variants, info, list_depth)
        elif node.name == "pre":
            code = node.find("code") or node
            language = None
            for parent in (code, node, node.parent):
                for cls in parent.get("class", []):
                    if cls.startswith("language-"):
                        language = cls.removeprefix("language-")
            if language is None and any(v["label"].startswith("Python ") for v in variants):
                language = "python"
            emit("code", code.get_text(), variants, callout, language=language)
        elif node.name == "table":
            rows = [
                [text(cell) for cell in row.find_all(["th", "td"], recursive=False)]
                for row in node.find_all("tr")
            ]
            emit("table", "\n".join(" | ".join(row) for row in rows), variants, callout, rows=rows)
        elif node.name in {"ul", "ol"}:
            start = int(node.get("start", 1))
            for index, item in enumerate(node.find_all("li", recursive=False), start=start):
                inline = []

                def flush(inline, index):
                    value = re.sub(r"\s+", " ", "".join(inline)).strip()
                    marker = f"{index}." if node.name == "ol" else "-"
                    emit("list", value, variants, callout, depth=list_depth, marker=marker)
                    inline.clear()

                for child in item.children:
                    if isinstance(child, Tag) and child.name == "p":
                        inline.append(text(child) + " ")
                    elif isinstance(child, Tag) and child.name in {"ul", "ol", "pre", "div"}:
                        flush(inline, index)
                        depth = list_depth + 1 if child.name in {"ul", "ol"} else list_depth
                        walk(child, variants, callout, depth)
                    elif isinstance(child, NavigableString):
                        inline.append(str(child))
                    elif isinstance(child, Tag):
                        inline.append(child.get_text())
                flush(inline, index)
        elif node.name == "p":
            emit("paragraph", text(node), variants, callout)
        elif node.name == "blockquote":
            emit("quote", text(node), variants, callout)
        else:
            for child in node.children:
                walk(child, variants, callout, list_depth)

    walk(article)
    code_blocks = sum(block["type"] == "code" for block in blocks)
    if code_blocks != len(article.find_all("pre")):
        raise ValueError("Extraction lost code blocks; inspect nested lists, quotes, or tables")
    prose = [block for block in blocks if block["type"] in {"paragraph", "list", "quote"}]
    if not prose or not code_blocks:
        raise ValueError("Article lacks meaningful prose or code; refusing navigation-only capture")
    document = {
        "parser_version": PARSER_VERSION,
        "url": url,
        "title": text(title),
        "blocks": blocks,
    }
    document["content_hash"] = json_hash(document)
    return document


def validate_page(document: dict, expected: dict) -> None:
    if document["title"] != expected["expected_title"]:
        raise ValueError(f"Unexpected page title: {document['title']!r}")
    code = "\n".join(block["text"] for block in document["blocks"] if block["type"] == "code")
    if expected["expected_code"] not in code:
        raise ValueError(f"Expected code example is missing: {expected['expected_code']}")
    anchor = expected.get("expected_section")
    if anchor and not any(
        block["type"] == "heading" and block["section_anchor"] == anchor
        for block in document["blocks"]
    ):
        raise ValueError(f"Expected section is missing: {anchor}")
