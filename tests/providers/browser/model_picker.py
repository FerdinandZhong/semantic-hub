"""Picker acceptance against an isolated Hub and local Helios review fixture."""

import argparse
import json
from pathlib import Path
import uuid
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--chromium")
parser.add_argument("--output", type=Path, default=Path("/tmp/semantic-picker-browser"))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
base = args.base_url.rstrip("/")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=args.chromium)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    provider = "picker-" + uuid.uuid4().hex[:8]
    response = page.request.post(
        base + "/api/semantic-hub/v2/providers",
        data={
            "id": provider,
            "name": "Local picker test",
            "ui_origin": "http://127.0.0.1:8200",
            "api_origin": "http://127.0.0.1:8201",
        },
    )
    assert response.status == 201
    page.goto(base + "/v2?view=providers", wait_until="networkidle")
    button = page.locator(f"[data-link-project={provider}]")
    submit = page.locator("#setup-form [type=submit]")
    button.click()
    page.locator("#helios-org").select_option("local-review")
    page.locator("#helios-model").select_option("empty-review")
    page.locator("[name=name]").fill("Linked review fixture")
    expect(submit).to_be_enabled()
    for width in (1440, 980, 390):
        page.set_viewport_size({"width": width, "height": 1000})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(args.output / f"picker-{width}.png"), full_page=True)
    submit.click()
    expect(page.locator("#setup")).not_to_be_visible()
    page.wait_for_url("**view=home**")
    expect(page.locator("#notice")).to_contain_text("Linked review fixture")
    records = page.request.get(base + "/api/semantic-hub/v2/workspaces").json()["items"]
    linked = next(row for row in records if row.get("provider_id") == provider)
    assert (
        linked["model_id"] == "empty-review"
        and linked["organization_id"] == "local-review"
    )
    assert linked["links"]["studio"].endswith(
        "organization=local-review&model=empty-review"
    )
    expect(page.locator(f'[data-open-workspace="{linked["id"]}"]')).to_be_visible()
    page.locator("[data-nav=providers]").click()

    pattern = "**/providers/" + provider + "/discover"
    page.route(
        pattern, lambda route: route.fulfill(status=401, json={"detail": "denied"})
    )
    button.click()
    expect(page.locator("#setup-error")).to_contain_text("valid CAI API key")
    expect(submit).to_be_disabled()
    page.locator("#helios-key").fill("browser-test-secret")
    page.keyboard.press("Escape")
    expect(page.locator("#setup")).not_to_be_visible()
    expect(page.locator("#helios-key")).to_have_value("")
    assert (
        page.evaluate(
            "JSON.stringify(localStorage)+JSON.stringify(sessionStorage)"
        ).find("browser-test-secret")
        == -1
    )
    page.unroute(pattern)

    page.route(
        pattern, lambda route: route.fulfill(json={"organizations": [], "models": []})
    )
    button.click()
    expect(page.locator("#helios-status")).to_contain_text(
        "No accessible organizations"
    )
    expect(submit).to_be_disabled()
    page.locator("#close-dialog").click()
    page.unroute(pattern)

    # A response from a closed dialog must not overwrite the reopened dialog.
    page.evaluate("""() => {
      const original = window.fetch;
      let held = false;
      window.fetch = (...args) => {
        if (!held && String(args[0]).endsWith('/discover')) {
          held = true;
          return new Promise(resolve => window.resolveOldDiscovery = () => resolve(
            new Response(JSON.stringify({organizations:[{id:'stale', name:'Stale'}],models:[]}),
              {status:200, headers:{'Content-Type':'application/json'}})));
        }
        return original(...args);
      };
    }""")
    button.click()
    page.wait_for_function('typeof window.resolveOldDiscovery === "function"')
    page.locator("#close-dialog").click()
    button.click()
    page.locator("#helios-org").select_option("local-review")
    page.evaluate("window.resolveOldDiscovery()")
    expect(page.locator("#helios-org")).to_have_value("local-review")
    assert page.locator("#helios-org option[value=stale]").count() == 0
    page.locator("#close-dialog").click()
    page.locator("#add-provider").click()
    expect(
        submit
    ).to_be_enabled()  # Disabled picker state must not leak to another form.
    page.locator("#close-dialog").click()
    assert not errors, errors
    print(
        json.dumps(
            {"passed": True, "page_errors": errors, "artifacts": str(args.output)}
        )
    )
    browser.close()
