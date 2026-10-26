"""Provider workspace mounted beside the existing v1 API and built-in Studio."""

from pathlib import Path
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from apps.helios.console.semantic_hub_api import authorize
from .providers.registry import Registry
from .shell import sidebar

WEB = Path(__file__).parent / "web"


class ProviderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=64)
    name: str = Field(max_length=120)
    ui_origin: str = Field(max_length=1000)
    api_origin: str = Field(max_length=1000)


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=160)
    provider_id: str = Field(max_length=64)
    organization_id: str = Field(max_length=160)
    model_id: str = Field(max_length=160)


def install(app, hub, state, *, local=False):
    registry = Registry(Path(state), local=local)
    app.state.provider_registry = registry
    router = APIRouter(prefix="/api/semantic-hub/v2", dependencies=[Depends(authorize)])

    def mutate(request, action):
        if not (
            request.app.state.local_no_auth
            or getattr(request.app.state, "platform_auth", False)
        ):
            raise HTTPException(
                403,
                "Consumer tokens are read-only. Configure providers through the authenticated Hub application.",
            )
        # Browser writes require local access or authenticated CAI ingress.
        supplied = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        if (supplied and supplied != expected) or request.headers.get(
            "sec-fetch-site"
        ) == "cross-site":
            raise HTTPException(403, "Cross-site writes are not allowed.")
        try:
            return action()
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.get("/providers")
    def providers():
        return {"items": registry.providers()}

    @router.post("/providers", status_code=201)
    def add_provider(body: ProviderInput, request: Request):
        return mutate(
            request,
            lambda: registry.save_provider(
                body.id, body.name, body.ui_origin, body.api_origin
            ),
        )

    @router.post("/projects", status_code=201)
    def add_project(body: ProjectInput, request: Request):
        return mutate(
            request,
            lambda: registry.add_project(
                body.name, body.provider_id, body.organization_id, body.model_id
            ),
        )

    @router.get("/workspaces")
    def workspaces():
        items = []
        for s in hub.catalog()["sources"]:
            items.append(
                dict(
                    id=s["id"],
                    name=s["name"],
                    provider_id="builtin",
                    provider_name="Built-in builder",
                    kind=s["kind"],
                    status=(s.get("model") or {}).get("status", "configured"),
                    model=s.get("model"),
                    description=s["description"],
                    native=True,
                    links={
                        "studio": "/v2/editor?" + urlencode({"source": s["id"]}),
                        "chat": (
                            "/v2?" + urlencode({"view": "chat", "workspace": s["id"]})
                            if s["kind"] == "local"
                            else None
                        ),
                        "sources": "/v2/editor?"
                        + urlencode({"source": s["id"]})
                        + "#source",
                    },
                )
            )
        for p in registry.projects():
            provider = registry.provider(p["provider_id"])
            items.append(
                p
                | dict(
                    provider_name=provider["name"],
                    kind="external",
                    status="linked",
                    native=False,
                    model=None,
                    description="Native provider workspace. Model access is checked by the provider.",
                    links=registry.links(p),
                )
            )
        return {"items": items}

    from .editor import install_editor
    from .support_pages import install_support_pages

    install_editor(app)
    install_support_pages(app)
    app.include_router(router)
    app.mount(
        "/v2/assets", StaticFiles(directory=WEB), name="provider-workspace-assets"
    )

    @app.get("/v2", include_in_schema=False)
    def page():
        html = (
            (WEB / "index.html")
            .read_text()
            .replace("<!-- HUB_SIDEBAR -->", sidebar("home"))
        )
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/", include_in_schema=False)
    @app.get("/v2/", include_in_schema=False)
    def landing():
        return RedirectResponse("/v2")
