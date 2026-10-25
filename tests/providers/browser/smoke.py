"""Browser smoke for an isolated Hub with the reviewed finance fixture."""

from playwright.sync_api import sync_playwright
import json
from pathlib import Path
import argparse
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--chromium")
parser.add_argument("--output", type=Path, default=Path("/tmp/semantic-v2-browser"))
args = parser.parse_args()
provider_id = "browser-" + uuid.uuid4().hex[:8]
workspace_name = "Native " + provider_id
out = args.output
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=args.chromium)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(
        args.base_url.rstrip("/") + "/v2?workspace=finance", wait_until="networkidle"
    )
    page.locator("[data-metric]").first.wait_for()
    page.screenshot(path=str(out / "studio.png"), full_page=True)
    page.locator("[data-view=tables]").click()
    page.locator("#table-preview td").first.wait_for()
    assert page.locator("#table-preview tbody tr").count() <= 10
    page.screenshot(path=str(out / "tables.png"), full_page=True)
    page.locator("[data-view=chat]").click()
    page.locator("[data-suggest]").first.click()
    page.locator("[data-run]").wait_for()
    page.locator("#question").fill("Changed question")
    assert page.locator("[data-run]").count() == 0
    page.locator("[data-suggest]").first.click()
    page.locator("[data-run]").wait_for()
    page.locator("[data-run]").click()
    page.locator("#chat-thread td").first.wait_for(timeout=30000)
    from decimal import Decimal

    assert Decimal(page.locator("#chat-thread td").first.inner_text()) == Decimal(
        "686572.96"
    )
    page.locator("#chat-thread td").first.scroll_into_view_if_needed()
    assert page.locator("#chat-thread td").first.evaluate(
        '(el)=>{const r=el.getBoundingClientRect(); const c=document.getElementById("chat-form").getBoundingClientRect(); return r.bottom <= c.top;}'
    )
    page.screenshot(path=str(out / "chat.png"), full_page=True)
    for width in [980, 390]:
        page.set_viewport_size({"width": width, "height": 1000})
        for view in ["studio", "sources", "tables", "chat", "providers"]:
            page.locator(f"[data-view={view}]").click()
            page.wait_for_timeout(250)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (width, view, page.evaluate("document.documentElement.scrollWidth"))
        page.screenshot(path=str(out / f"providers-{width}.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.get_by_role("button", name="Connect Helios", exact=True).click()
    for key, value in dict(
        id=provider_id,
        name="Browser test",
        ui_origin="http://127.0.0.1:8100",
        api_origin="http://127.0.0.1:8101",
    ).items():
        page.locator(f"[name={key}]").fill(value)
    page.get_by_role("button", name="Save", exact=True).click()
    page.locator(f"[data-link-project={provider_id}]").click()
    for key, value in dict(
        name=workspace_name, organization_id="org-id", model_id="model-id"
    ).items():
        page.locator(f"[name={key}]").fill(value)
    page.get_by_role("button", name="Save", exact=True).click()
    page.locator("#workspace option").filter(has_text=workspace_name).wait_for(
        state="attached"
    )
    page.locator("#workspace").select_option(label=workspace_name)
    page.locator("[data-view=studio]").click()
    link = page.get_by_role("link", name="Open Studio")
    assert (
        link.get_attribute("href")
        == "http://127.0.0.1:8100/canvas?organization=org-id&model=model-id"
    )
    assert not errors, errors
    print(json.dumps({"passed": True, "page_errors": errors, "artifacts": str(out)}))
    browser.close()
