from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from fastapi_docs_rag.parse import parse_page, validate_page

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://fastapi.tiangolo.com/tutorial/dependencies/"


def test_structure_and_code_preservation():
    document = parse_page((FIXTURES / "structure.html").read_bytes(), URL)
    assert document["title"] == "Example"
    blocks = document["blocks"]
    code = [block for block in blocks if block["type"] == "code"]
    assert code[0]["text"] == 'def modern():\n    return "évidence"\n'
    assert code[0]["language"] == "python"
    assert code[0]["variants"] == [
        {"group": "tabs-1", "index": 0, "label": "Python 3.10+ Annotated"}
    ]
    assert code[1]["variants"][0]["label"] == "Python 3.9+ legacy"
    assert code[2]["callout"] == {"title": "Warning", "kind": "warning"}
    assert code[2]["heading_path"] == ["Example", "Variants", "Resource warning"]
    assert code[2]["section_anchor"] == "warning"
    table = next(block for block in blocks if block["type"] == "table")
    assert table["rows"] == [["Setting", "Value"], ["limit", "10"]]
    items = [block for block in blocks if block["type"] == "list"]
    assert [(block["text"], block["depth"]) for block in items] == [
        ("First item", 0),
        ("Nested item", 1),
        ("Second item", 0),
    ]
    assert blocks[-1]["section_anchor"] is None
    assert "Navigation noise" not in str(document)
    assert "ignore_this" not in str(document)


def test_deterministic_hash_ignores_navigation():
    html = (FIXTURES / "structure.html").read_bytes()
    assert parse_page(html, URL) == parse_page(html, URL)
    assert (
        parse_page(html, URL)["content_hash"]
        == parse_page(html.replace(b"Navigation noise", b"New navigation"), URL)["content_hash"]
    )
    assert (
        parse_page(html, URL)["content_hash"]
        != parse_page(html.replace(b"Always close", b"Never close"), URL)["content_hash"]
    )


@pytest.mark.parametrize(
    "html",
    [
        b"<nav>Navigation only</nav>",
        b'<article class="md-content__inner"><h1>Menu</h1><nav>Links</nav></article>',
        b'<article class="md-content__inner"><p>No title</p></article>',
    ],
)
def test_changed_layout_fails(html):
    with pytest.raises(ValueError):
        parse_page(html, URL)


def test_malformed_tab_group_fails():
    html = (
        (FIXTURES / "structure.html")
        .read_bytes()
        .replace(b'<label for="tab-2">Python 3.9+ legacy</label>', b"")
    )
    with pytest.raises(ValueError, match="tab"):
        parse_page(html, URL)


def test_missing_expected_title_or_code_fails():
    document = parse_page((FIXTURES / "structure.html").read_bytes(), URL)
    with pytest.raises(ValueError, match="title"):
        validate_page(document, {"expected_title": "Wrong", "expected_code": "modern"})
    with pytest.raises(ValueError, match="code"):
        validate_page(document, {"expected_title": "Example", "expected_code": "missing_code"})


def test_long_code_not_truncated():
    code = "def example():\n" + "    yield resource\n" * 1000
    html = (
        '<article class="md-content__inner"><h1>Example</h1><p>Resource.</p>'
        f"<pre><code>{code}</code></pre></article>"
    )
    document = parse_page(html.encode(), URL)
    assert next(block["text"] for block in document["blocks"] if block["type"] == "code") == code


@pytest.mark.parametrize(
    "name, title, expected_code",
    [
        ("first-steps", "First Steps", '    return {"message": "Hello World"}'),
        ("dependencies", "Dependencies", "Annotated"),
        ("yield", "Dependencies with yield", "yield db"),
    ],
)
def test_real_fastapi_excerpts(name, title, expected_code):
    html = (FIXTURES / f"{name}.html").read_bytes()
    document = parse_page(html, URL)
    assert document["title"] == title
    code = [block for block in document["blocks"] if block["type"] == "code"]
    soup = BeautifulSoup(html, "html.parser")
    assert [block["text"] for block in code] == [
        pre.code.get_text() for pre in soup.find_all("pre")
    ]
    assert expected_code in code[0]["text"]
    assert code[0]["variants"][0]["label"] == "Python 3.10+"
    anchors = {node["id"] for node in soup.find_all(id=True)}
    assert all(
        block["section_anchor"] is None or block["section_anchor"] in anchors
        for block in document["blocks"]
    )


def test_missing_expected_section_fails():
    document = parse_page((FIXTURES / "structure.html").read_bytes(), URL)
    with pytest.raises(ValueError, match="section"):
        validate_page(
            document,
            {
                "expected_title": "Example",
                "expected_code": "modern",
                "expected_section": "missing-anchor",
            },
        )


def test_headings_inside_tabs_are_local():
    html = (
        (FIXTURES / "structure.html")
        .read_bytes()
        .replace(
            b'<div class="tabbed-block"><div class="highlight">',
            b'<div class="tabbed-block"><h3 id="modern-only">Modern details</h3>'
            b'<div class="highlight">',
        )
        .replace(b'<h3 id="warning">', b'<p>Shared explanation.</p><h3 id="warning">')
    )
    document = parse_page(html, URL)
    code = [block for block in document["blocks"] if block["type"] == "code"]
    assert code[0]["section_anchor"] == "modern-only"
    assert code[1]["section_anchor"] == "variants"
    shared = next(block for block in document["blocks"] if block["text"] == "Shared explanation.")
    assert shared["section_anchor"] == "variants"


def test_loose_ordered_lists_preserve_numbering():
    html = (
        (FIXTURES / "structure.html")
        .read_bytes()
        .replace(b"<ul><li>First", b'<ol start="4"><li><p>First')
        .replace(b"item</code><ul>", b"item</code></p><ul>")
        .replace(b"<li>Second item</li></ul>", b"<li><p>Second item</p></li></ol>")
    )
    document = parse_page(html, URL)
    items = [block for block in document["blocks"] if block["type"] == "list"]
    assert [(block["text"], block["marker"], block["depth"]) for block in items] == [
        ("First item", "4.", 0),
        ("Nested item", "-", 1),
        ("Second item", "5.", 0),
    ]
