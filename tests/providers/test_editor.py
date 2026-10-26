from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from semantic_hub.editor import CONSOLE, editor_script, install_editor


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.items = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def client():
    app = FastAPI()
    install_editor(app)
    return TestClient(app)


def test_editor_uses_one_shared_shell_and_five_workflow_destinations():
    response = client().get("/v2/editor?source=payments")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    elements = Elements(response.text).items
    assert len([tag for tag, _ in elements if tag == "aside"]) == 1
    assert not any(tag == "iframe" for tag, _ in elements)
    links = [attrs for tag, attrs in elements if tag == "a"]
    workspace = next(a for a in links if a.get("data-nav") == "workspace")
    assert workspace["aria-current"] == "page"
    assert parse_qs(urlsplit(workspace["href"]).query) == {
        "view": ["overview"],
        "workspace": ["payments"],
    }
    overview = next(a for a in links if a.get("class") == "overview-tab")
    assert overview["href"] == workspace["href"]
    tabs = [a["data-step"] for _, a in elements if "data-step" in a]
    assert tabs == ["source", "define", "validate", "review"]
    assert all(not a.get("href", "").startswith("/demo") for a in links)
    assert not any("target" in a for a in links)


def test_editor_preserves_all_existing_ids_forms_and_canvas_hooks():
    original = Elements((CONSOLE / "templates/demo-context.html").read_text()).items
    rendered = Elements(client().get("/v2/editor?source=payments").text).items
    original_ids = [a["id"] for _, a in original if "id" in a]
    rendered_ids = [a["id"] for _, a in rendered if "id" in a]
    assert set(original_ids) <= set(rendered_ids)
    assert len(rendered_ids) == len(set(rendered_ids))
    for tag in ("input", "textarea", "select", "form", "dialog"):
        assert [a for t, a in original if t == tag] == [
            a for t, a in rendered if t == tag
        ]
    scripts = [a["src"] for t, a in rendered if t == "script"]
    assert "/static/demo-canvas.js" in scripts
    assert "/v2/editor-assets/context.js" in scripts
    assert "/static/demo-context.js" not in scripts


def test_source_is_encoded_as_data_without_html_or_script_injection():
    source = '"><script>alert(1)</script>&workspace=other'
    response = client().get("/v2/editor", params={"source": source})
    assert "<script>alert(1)</script>" not in response.text
    for tag, attrs in Elements(response.text).items:
        if tag == "a" and attrs.get("data-nav") in ("workspace", "chat"):
            assert parse_qs(urlsplit(attrs["href"]).query)["workspace"] == [source]


def test_script_keeps_api_contract_dirty_guard_and_internal_version_links():
    response = client().get("/v2/editor-assets/context.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    script = response.text
    original = (CONSOLE / "static/demo-context.js").read_text()
    for line in original.splitlines():
        if "/demo/api/" in line:
            assert line in script
    assert 'window.addEventListener("beforeunload",event=>{' in script
    assert (
        'if(dirty){\n    event.preventDefault();\n    event.returnValue="";' in script
    )
    assert 'new URL("/v2/editor",location.origin)' in script
    assert 'new URL("/v2/materials",location.origin)' in script
    assert 'if(location.hash==="#define")return "define";' in editor_script()
    assert 'if(location.hash==="#review")return "review";' in editor_script()
