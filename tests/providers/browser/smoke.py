"""Browser acceptance for an isolated Hub with a reviewed finance test fixture."""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import uuid
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--chromium")
parser.add_argument("--output", type=Path, default=Path("/tmp/semantic-v2-browser"))
args = parser.parse_args()
base = args.base_url.rstrip("/")
args.output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=args.chromium)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/v2", wait_until="networkidle")
    page.locator(".workspace-card").first.wait_for()
    assert page.locator("#workspace-bar").is_hidden()
    assert page.locator(".sidebar").count() == 1
    assert page.locator(".sidebar svg").count() == 5
    page.locator("#workspace-search").fill("Finance sample")
    assert page.locator(".workspace-card").count() == 1
    page.screenshot(path=str(args.output / "catalog.png"), full_page=True)
    page.locator("[data-open-workspace=finance]").click()
    page.get_by_role("heading", name="Build and publish").wait_for()
    assert page.locator("#workspace-tabs a").count() == 5
    page.screenshot(path=str(args.output / "overview.png"), full_page=True)
    page.locator("[data-nav=home]").click()
    page.locator("#new-workspace").click()
    page.locator("#create-builtin").click()
    page.locator("[name=name]").fill("Browser workspace " + uuid.uuid4().hex[:8])
    page.locator('[name="config.pack_id"]').select_option("finance")
    page.locator("#setup-form button[type=submit]").click()
    page.wait_for_url("**workspace=source-*")
    page.get_by_role("heading", name="Build and publish").wait_for()
    assert "Not published" in page.locator("#content").inner_text()
    page.goto(base + "/v2?view=chat&workspace=finance", wait_until="networkidle")
    page.locator("[data-suggest]").first.click()
    page.locator("[data-run]").wait_for()
    page.locator("#question").fill("Changed question")
    assert page.locator("[data-run]").count() == 0
    page.locator("[data-suggest]").first.click()
    page.locator("[data-run]").click()
    page.locator("#chat-thread td").first.wait_for(timeout=30000)
    assert Decimal(page.locator("#chat-thread td").first.inner_text()) == Decimal(
        "686572.96"
    )
    page.screenshot(path=str(args.output / "chat.png"), full_page=True)
    routes = {
        "catalog": "/v2",
        "overview": "/v2?view=overview&workspace=finance",
        "chat": "/v2?view=chat&workspace=finance",
        "providers": "/v2?view=providers",
        "settings": "/v2/settings?source=finance",
        "materials": "/v2/materials?source=finance",
    }
    for width in (1440, 980, 390):
        page.set_viewport_size({"width": width, "height": 1000})
        for name, path in routes.items():
            page.goto(base + path, wait_until="networkidle")
            assert page.locator(".sidebar").count() == 1, (name, "sidebar")
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (width, name, page.evaluate("document.documentElement.scrollWidth"))
            if width == 1440:
                page.screenshot(path=str(args.output / (name + ".png")), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(base + "/v2?view=providers", wait_until="networkidle")
    page.locator("#add-provider").click()
    provider = "browser-" + uuid.uuid4().hex[:8]
    for key, value in dict(
        id=provider,
        name="Browser provider",
        ui_origin="http://127.0.0.1:8200",
        api_origin="http://127.0.0.1:8201",
    ).items():
        page.locator(f"[name={key}]").fill(value)
    page.locator("#setup-form button[type=submit]").click()
    page.locator(f"[data-link-project={provider}]").click()
    workspace = "Native " + provider
    for key, value in dict(
        name=workspace, organization_id="org-id", model_id="model-id"
    ).items():
        page.locator(f"[name={key}]").fill(value)
    page.locator("#setup-form button[type=submit]").click()
    page.locator("[data-nav=home]").click()
    page.locator("#workspace-search").fill(workspace)
    page.locator("[data-open-workspace]").click()
    link = page.get_by_role("link", name="Open Studio")
    assert (
        link.get_attribute("href")
        == "http://127.0.0.1:8200/canvas?organization=org-id&model=model-id"
    )
    assert "Navigation only" in page.locator("#content").inner_text()
    assert not errors, errors
    print(
        json.dumps(
            {"passed": True, "page_errors": errors, "artifacts": str(args.output)}
        )
    )
    browser.close()
