"""The shared shell must retain the real settings and evidence workflows."""

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from semantic_hub.support_pages import CONSOLE, install_support_pages


@pytest.fixture
def client():
    app = FastAPI()
    install_support_pages(app)
    return TestClient(app)


@pytest.mark.parametrize(
    "route,kind", [("settings", "llm"), ("materials", "materials")]
)
def test_real_workflows_keep_dom_and_shared_navigation(client, route, kind):
    response = client.get(f"/v2/{route}?source=payments")
    assert response.status_code == 200
    html = response.text
    original = (CONSOLE / "templates" / f"demo-{kind}.html").read_text()
    assert set(re.findall(r'id="([^"]+)"', original)) <= set(
        re.findall(r'id="([^"]+)"', html)
    )
    assert 'class="sidebar"' in html
    assert 'class="main"' in html
    assert html.count("<header>") == 1
    assert "<iframe" not in html
    assert "/static/demo.css" not in html
    assert "/static/demo-shell.css" not in html
    assert "/demo/context" not in html
    assert 'data-source="payments"' in html
    assert f"/v2/support-assets/{kind}.js" in html


def test_source_context_is_escaped(client):
    html = client.get(
        "/v2/materials", params={"source": '"><script>alert(1)</script>'}
    ).text
    assert '"><script>alert(1)</script>' not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("kind", ["llm", "materials"])
def test_original_api_and_credentials_behavior_is_retained(client, kind):
    original = (CONSOLE / "static" / f"demo-{kind}.js").read_text()
    response = client.get(f"/v2/support-assets/{kind}.js")
    assert response.status_code == 200
    assert response.text == original.replace("/demo/context", "/v2/editor")
    assert "/demo/api/" in response.text


@pytest.mark.parametrize("kind", ["llm", "materials"])
def test_legacy_styles_cannot_escape_support_content(client, kind):
    css = client.get(f"/v2/support-assets/{kind}.css").text
    assert css.startswith("@scope (.support-content) {")
    assert ":root" not in css
    assert "body {" not in css
    assert css.endswith("\n}")


def test_only_known_support_assets_are_exposed(client):
    assert client.get("/v2/support-assets/demo.py").status_code == 404


def test_source_materials_remain_in_workspace_navigation(client):
    html = client.get("/v2/materials", params={"source": "finance & cash"}).text
    assert 'id="support-workspace-name">finance &amp; cash</strong>' in html
    assert 'aria-label="Workspace workflow"' in html
    assert 'class="active" aria-current="page">Source data</a>' in html
    for step in ("source", "define", "validate", "hub"):
        assert f"/v2/editor?source=finance+%26+cash#{step}" in html
    assert "/v2?view=overview&amp;workspace=finance+%26+cash" in html


def test_global_settings_and_library_do_not_show_workspace_tabs(client):
    for route in ("/v2/settings?source=finance", "/v2/materials"):
        assert 'aria-label="Workspace workflow"' not in client.get(route).text
