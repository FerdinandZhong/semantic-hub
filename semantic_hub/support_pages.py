"""Render existing model and evidence workflows inside the shared Hub shell.

The original scripts continue to use the existing authenticated demo APIs.
Only presentation and Studio navigation change here.
"""

from html import escape
from pathlib import Path
from urllib.parse import urlencode
import re

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

CONSOLE = Path(__file__).resolve().parents[1] / "apps" / "helios" / "console"
WEB = Path(__file__).parent / "web"


def render_support_page(kind: str, source: str = "") -> str:
    from .shell import sidebar

    template = (CONSOLE / "templates" / f"demo-{kind}.html").read_text()
    content = template.split("<main>", 1)[1].split("</main>", 1)[0]
    content = re.sub(r"<header>.*?</header>", "", content, count=1, flags=re.S)
    content = content.replace("/demo/context", "/v2/editor")
    title = "Model configuration" if kind == "llm" else "Supporting materials"
    active = "settings" if kind == "llm" else "workspace"
    source_attr = escape(source, quote=True)
    workspace_context = ""
    if kind == "materials" and source:
        overview = "/v2?" + urlencode({"view": "overview", "workspace": source})
        editor = "/v2/editor?" + urlencode({"source": source})
        tabs = [
            ("Overview", overview, False),
            ("Source data", editor + "#source", True),
            ("Studio", editor + "#define", False),
            ("Validation & review", editor + "#validate", False),
            ("Versions & releases", editor + "#hub", False),
        ]
        tab_html = "".join(
            f'<a href="{escape(url, quote=True)}"'
            + (' class="active" aria-current="page"' if active else "")
            + f">{label}</a>"
            for label, url, active in tabs
        )
        workspace_context = (
            '<div class="support-workspace-context"><span>Semantic workspace</span>'
            f'<strong id="support-workspace-name">{escape(source)}</strong>'
            '<span class="support-workspace-builder">Built-in builder</span></div>'
            '<nav class="workspace-tabs support-workspace-tabs" aria-label="Workspace workflow">'
            + tab_html
            + "</nav>"
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Semantic Hub · {title}</title>
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/v2/assets/workspace.css">
<link rel="stylesheet" href="/v2/assets/support-shell.css">
<link rel="stylesheet" href="/v2/support-assets/{kind}.css">
<script src="/v2/assets/support-shell.js" defer></script>
<script src="/v2/support-assets/{kind}.js" defer></script>
</head><body data-support-page="{kind}" data-source="{source_attr}">
{sidebar(active, source)}<main class="main">
<header><div><b>Semantic Hub</b><span class="slash">/</span>{title}</div>
<span>Built-in workflow</span></header>
{workspace_context}<div class="support-content">{content}</div></main></body></html>"""


def install_support_pages(app):
    @app.get("/v2/settings", response_class=HTMLResponse, include_in_schema=False)
    def settings(request: Request):
        return render_support_page("llm", request.query_params.get("source", ""))

    @app.get("/v2/materials", response_class=HTMLResponse, include_in_schema=False)
    def materials(request: Request):
        return render_support_page("materials", request.query_params.get("source", ""))

    @app.get("/v2/support-assets/{asset}", include_in_schema=False)
    def support_asset(asset: str):
        if asset not in {"llm.css", "llm.js", "materials.css", "materials.js"}:
            return Response(status_code=404)
        kind, extension = asset.split(".")
        original = (CONSOLE / "static" / f"demo-{kind}.{extension}").read_text()
        if extension == "js":
            return Response(
                original.replace("/demo/context", "/v2/editor"),
                media_type="application/javascript",
            )
        # Native CSS scope prevents original global selectors from changing the shell.
        base = (CONSOLE / "static" / "demo.css").read_text()
        scoped = re.sub(r":root|\bbody(?=\s*\{)", ":scope", base + "\n" + original)
        return Response(
            "@scope (.support-content) {\n" + scoped + "\n}", media_type="text/css"
        )
