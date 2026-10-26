"""Shared navigation for every Hub page; native providers keep their own application."""

from html import escape
from urllib.parse import urlencode

ICONS = {
    "home": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "workspace": '<path d="m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    "chat": '<path d="M21 11a8 8 0 0 1-8 8H5l-3 3V7a4 4 0 0 1 4-4h7a8 8 0 0 1 8 8Z"/><path d="M7 8h9M7 12h6"/>',
    "providers": '<path d="M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-12 0V8ZM12 17v4"/>',
    "settings": '<path d="M3 7h18M3 17h18"/><circle cx="8" cy="7" r="3" fill="white"/><circle cx="16" cy="17" r="3" fill="white"/>',
}


def sidebar(active: str, source: str = "") -> str:
    links = [
        ("home", "Workspaces", "/v2"),
        (
            "workspace",
            "Semantic workspace",
            "/v2?" + urlencode({"view": "overview", "workspace": source}),
        ),
        (
            "chat",
            "Talk to your data",
            "/v2?" + urlencode({"view": "chat", "workspace": source}),
        ),
        ("providers", "Builders & connections", "/v2?view=providers"),
        (
            "settings",
            "Model configuration",
            "/v2/settings?" + urlencode({"source": source}),
        ),
    ]
    items = []
    for key, label, url in links:
        svg = (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            + ICONS[key]
            + "</svg>"
        )
        selected = ' class="active" aria-current="page"' if active == key else ""
        items.append(
            f'<a data-nav="{key}" href="{escape(url, quote=True)}"{selected}>{svg}<span>{label}</span></a>'
        )
    return (
        '<aside class="sidebar"><a class="brand" href="/v2"><img src="/static/cloudera-wordmark.png" alt="Cloudera"><span>SEMANTIC HUB</span></a><span class="nav-label">WORKSPACE</span><nav aria-label="Workspace">'
        + "".join(items)
        + '</nav><div class="sidebar-bottom">One workspace.<br>Build, review, publish, and ask.</div></aside>'
    )
