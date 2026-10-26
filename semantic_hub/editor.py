"""Render the existing built-in Studio within the shared Hub navigation."""

from html import escape
from pathlib import Path
import re
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse, Response

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "apps" / "helios" / "console"
WEB = Path(__file__).parent / "web"


def render_editor(source: str = "") -> str:
    from .shell import sidebar

    page = (CONSOLE / "templates" / "demo-context.html").read_text()
    page = re.sub(
        r"<aside>.*?</aside>", sidebar("workspace", source), page, count=1, flags=re.S
    )
    page = page.replace("<body>", '<body class="hub-editor">')
    page = page.replace("<main>", '<main class="main editor-main">', 1)
    page = page.replace(
        "Local sample workspace</span></header>",
        "Built-in workspace</span></header>",
        1,
    )
    page = page.replace(
        '<script src="/static/demo-context.js" defer></script>',
        '<script src="/v2/editor-assets/context.js" defer></script>'
        '<script src="/v2/assets/editor-shell.js" defer></script>',
    )
    page = re.sub(
        r'<link rel="stylesheet" href="/static/demo-shell.css[^\"]*">', "", page
    )
    page = page.replace(
        "</head>",
        '<link rel="stylesheet" href="/v2/assets/workspace.css">'
        '<link rel="stylesheet" href="/v2/assets/editor-shell.css"></head>',
    )
    overview = escape(
        "/v2?" + urlencode({"view": "overview", "workspace": source}), quote=True
    )
    page = page.replace(
        '<div class="steps" role="tablist" aria-label="Context workflow">',
        '<nav class="steps editor-steps" aria-label="Workspace workflow">'
        f'<a class="overview-tab" href="{overview}">Overview</a>'
        '<div class="editor-tabs" role="tablist" aria-label="Editing workflow">',
    )
    page = page.replace(
        '    </div>\n    <section id="step-source"',
        '    </div></nav>\n    <section id="step-source"',
        1,
    )
    # Keep workspace identity and workflow above the editor's save toolbar.
    workflow = re.search(r'<nav class="steps editor-steps".*?</nav>', page, re.S)
    if workflow:
        page = page[: workflow.start()] + page[workflow.end() :]
        page = page.replace(
            '<div class="workspace-bar">',
            workflow.group() + '<div class="workspace-bar">',
            1,
        )
    page = page.replace("</header>", '</header><div class="editor-content">', 1)
    page = page.replace("</main>", "</div></main>", 1)
    # These anchors are private hooks used by the original editor script.
    # Keep them out of navigation so the shared sidebar remains authoritative.
    page = page.replace(
        '<section class="heading">',
        '<div hidden aria-hidden="true"><a id="nav-studio"></a>'
        '<a id="nav-versions"></a><span id="source-nav-title"></span></div>'
        '<section class="heading">',
        1,
    )
    page = page.replace('href="/demo/materials"', 'href="/v2/materials"')
    chat = escape("/v2?" + urlencode({"view": "chat", "workspace": source}), quote=True)
    page = page.replace('href="/demo/query" data-source-link', f'href="{chat}"')
    return page


def editor_script() -> str:
    """Keep editor behavior and API paths, changing only page navigation."""
    script = (CONSOLE / "static" / "demo-context.js").read_text()
    script = script.replace(
        "function stepFromHash() {",
        "function stepFromHash() {\n"
        '  if(location.hash==="#define")return "define";\n'
        '  if(location.hash==="#review")return "review";',
    )
    script = script.replace(
        "currentSource=config.connection_id;",
        "currentSource=config.connection_id;\n"
        "  window.HubEditorShell?.setSource(currentSource);",
    )
    script = script.replace(
        '$("workspace-heading").textContent=title;',
        '$("workspace-heading").textContent=config?.connection_name '
        "? `${config.connection_name} · ${title}` : title;",
    )
    script = script.replace(
        '$("pack-title").textContent=config.title;',
        '$("pack-title").textContent=config.title;\n'
        '  $("workspace-heading").textContent=`${config.connection_name} · '
        '${$("step-review").hidden ? "Semantic Studio" : "Versions & releases"}`;',
    )
    script = script.replace(
        'new URL("/demo/context",location.origin)',
        'new URL("/v2/editor",location.origin)',
    )
    return script.replace(
        'new URL("/demo/materials",location.origin)',
        'new URL("/v2/materials",location.origin)',
    )


def install_editor(app):
    @app.get("/v2/editor", response_class=HTMLResponse, include_in_schema=False)
    def editor(source: str = ""):
        return HTMLResponse(
            render_editor(source), headers={"Cache-Control": "no-store"}
        )

    @app.get("/v2/editor-assets/context.js", include_in_schema=False)
    def context_script():
        return Response(editor_script(), media_type="application/javascript")
