"""Context-builder interaction checks used by check_demo_browser.py --context-builder."""

import json

from playwright.sync_api import expect
from helios_core.ossie.model import SemanticModel


def batch_decision(page, decision="approve"):
    page.locator("#select-all").click()
    page.locator("#approve-selected" if decision == "approve" else "#request-selected").click()
    expect(page.locator("#batch-dialog")).to_be_visible()
    title = page.locator("#batch-title").bounding_box()
    preview = page.locator("#batch-preview").bounding_box()
    assert title["y"] + title["height"] <= preview["y"], "Batch heading overlaps the summary"
    assert page.locator("#batch-dialog").evaluate("e => e.scrollWidth <= e.clientWidth"), "Batch dialog overflows horizontally"
    assert page.locator("#batch-objects").bounding_box()["width"] > 250, "Selected objects collapsed into a narrow column"
    page.locator("#batch-reviewer").fill("automated-browser-test-only")
    page.locator("#batch-note").fill("Checked selected definitions and independent reconciliation evidence.")
    page.locator("#batch-confirmed").check()
    page.locator("#batch-submit").click()
    expect(page.locator("#batch-dialog")).not_to_be_visible()
    expect(page.locator("#notice")).to_contain_text("decisions recorded", timeout=30000)


def check_context_builder(page, base, pack, reference, width, output):
    previous = page.request.get(base + "/demo/api/config").json()
    page.goto(base + "/demo/context", wait_until="networkidle")
    expect(page.locator("#studio-canvas .canvas-node").first).to_be_visible()
    expect(page.get_by_role("img", name="Cloudera", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(output / f"{pack.entry.id}-studio-canvas-{width}.png"), full_page=True)
    # Layout changes must not alter the semantic revision or its validation state.
    before_layout = page.evaluate("window.contextStudio.getState().workspace.draft")
    page.get_by_role("button", name="Zoom in", exact=True).click()
    page.get_by_role("button", name="Fit", exact=True).click()
    assert page.evaluate("window.contextStudio.getState().workspace.draft") == before_layout
    assert not page.evaluate("window.contextStudio.getState().dirty")
    page.locator("#tab-validate").click()
    expect(page.locator("#review-items .review-technical").first).to_contain_text("Not validated")
    assert page.locator("#review-items td").evaluate_all(
        "cells => cells.every(cell => getComputedStyle(cell).display === 'table-cell')"
    )
    page.locator("#tab-source").click()
    expect(page.locator("#table-detail")).to_be_visible()
    expect(page.locator("#table-list button")).to_have_count(len(pack.tables))
    assert page.locator("#preview tbody tr").count() <= 10
    page.locator("#table-list button").last.click()
    expect(page.locator("#table-name")).to_have_text(pack.tables[-1].name)
    page.locator("#columns input").first.fill("Reviewed source identifier for the local sample")
    expect(page.locator("#draft-status")).to_contain_text("Unsaved changes")
    expect(page.locator("#review-items .review-technical").first).to_contain_text("Unsaved changes")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(
        path=str(output / f"{pack.entry.id}-builder-source-{width}.png"), full_page=True
    )
    page.locator("#tab-define").click()
    metric_name = page.locator("#metric-name").input_value()
    # First prove that a saved draft with missing reference evidence cannot pass.
    page.locator("#metric-reference_sql").fill("")
    page.locator("#save").click()
    expect(page.locator("#save")).to_be_disabled()
    page.locator("#tab-validate").click()
    page.locator("#validate").click()
    expect(page.locator("#validation-results")).to_contain_text(
        "Supply reviewer-authored reference SQL", timeout=30000
    )
    expect(page.locator("#review-items .review-technical").first).to_contain_text("Ready for review")
    page.locator("#review-filter").fill(metric_name)
    metric_review = page.locator("#review-items tr").filter(has_text=metric_name + " · metric")
    expect(metric_review.locator(".review-technical")).to_contain_text("Blocked")
    expect(metric_review.locator(".review-reason")).to_contain_text("Supply reviewer-authored reference SQL")
    page.locator("#review-filter").fill("")
    if pack.entry.id == "power" and width == 1440:
        batch_decision(page)
        expect(page.locator("#notice")).to_contain_text("1 rejected")
        items = page.request.get(base + "/demo/api/context").json()["review"]["items"]
        assert any(item["status"] == "approved" for item in items)
        assert next(item for item in items if item["name"] == metric_name)["status"] == "pending"
    page.locator("#tab-review").click()
    expect(page.locator("#review")).to_be_disabled()
    expect(page.locator("#review-blockers")).to_contain_text("Supply reviewer-authored reference SQL")
    page.get_by_role("button", name="Add reference SQL: " + metric_name, exact=True).click()
    expect(page.locator("#metric-reference_sql")).to_be_focused()
    page.locator("#metric-reference_sql").fill(
        reference["reference_sql"].replace("AS value", "AS " + metric_name)
    )
    if width == 1440:
        model = SemanticModel(pack.model_document())
        fact = model.metric(metric_name).dataset
        field = next(iter(model.datasets[fact].fields))
        page.locator("#add-metric").click()
        for key, value in {
            "name": "record_count",
            "description": "How many source records are available?",
            "grain": "All source records",
            "expression": f"COUNT({fact}.{field})",
            "reference_sql": f"SELECT COUNT(*) AS record_count FROM {fact}",
        }.items():
            page.locator("#metric-" + key).fill(value)
        if pack.entry.id == "power":
            page.locator("#metric-dimensions").fill("meters.customer_class")
            page.locator("#metric-grain").fill("Customer class")
            page.locator("#metric-reference_sql").fill(
                "SELECT m.customer_class AS customer_class, COUNT(*) AS record_count FROM meter_readings r JOIN meters m ON r.meter_id=m.meter_id GROUP BY m.customer_class"
            )
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(
        path=str(output / f"{pack.entry.id}-builder-definition-{width}.png"), full_page=True
    )
    page.locator("#save").click()
    expect(page.locator("#save")).to_be_disabled()
    page.locator("#tab-validate").click()
    page.locator("#validate").click()
    expect(page.locator("#validation-status")).to_have_text(
        "All checks passed for this saved draft.", timeout=30000
    )
    expect(page.locator("#validation-results .pass")).to_have_count(2)
    expect(page.locator("#review-items .review-technical .fail")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(
        path=str(output / f"{pack.entry.id}-builder-validation-{width}.png"), full_page=True
    )
    page.locator("#tab-review").click()
    expect(page.locator("#review")).to_be_disabled()
    page.locator("#tab-validate").click()
    if pack.entry.id == "power" and width == 1440:
        expect(page.locator("#review-items input[type=checkbox]").first).to_be_enabled()
        page.locator("#review-items input[type=checkbox]").first.check()
        expect(page.locator("#selection-count")).to_contain_text("1 selected")
        page.locator("#clear-selection").click()
        batch_decision(page, "request_changes")
        expect(page.locator("#review-items")).to_contain_text("changes requested")
        page.locator("#tab-review").click()
        expect(page.locator("#review")).to_be_disabled()
        page.locator("#tab-validate").click()
    batch_decision(page)
    expect(page.locator("#review-items")).to_contain_text("approved", timeout=30000)
    page.locator("#tab-review").click()
    expect(page.locator("#review-blockers")).not_to_be_visible()
    expect(page.locator("#review")).to_be_enabled()
    page.locator("#version").fill(f"browser-{width}")
    page.locator("#reviewer").fill("automated-browser-test-only")
    page.locator("#review-note").fill(
        "Verified source keys, metric rules and independent SQL reconciliation."
    )
    page.locator("#confirmed").check()
    page.locator("#review").click()
    expect(page.locator("#versions")).to_contain_text(f"browser-{width}")
    version_row = page.locator(".version-row").filter(
        has=page.get_by_role("link", name=f"browser-{width}", exact=True)
    )
    saved_before_view = page.request.get(base + "/demo/api/context").json()
    view_mutations = []
    def capture_view_request(request):
        if request.method not in ("GET", "HEAD"):
            view_mutations.append(request.url)
    page.on("request", capture_view_request)
    version_row.get_by_role("link", name=f"browser-{width}", exact=True).click()
    expect(page.locator("#version-detail")).to_be_visible()
    inspected = json.loads(page.locator("#version-json").text_content())
    assert len(inspected["definition"]["metrics"]) == 2
    assert all(item["status"] == "approved" for item in inspected["item_review"]["items"])
    expect(page.locator("#version-heading")).to_contain_text("Read-only")
    assert page.locator("input:visible:not(#version-canvas input), textarea:visible, select:visible:not(#version-canvas select)").count() == 0
    expect(page.locator("#version-canvas .canvas-node").first).to_be_visible()
    assert page.locator("#version-canvas .canvas-connect-handle").count() == 0
    assert page.locator("#version-canvas").get_by_role("button", name="Edit", exact=True).count() == 0
    assert page.locator("body").evaluate("el => el.scrollWidth <= innerWidth")
    page.reload(wait_until="networkidle")
    expect(page.locator("#version-detail")).to_be_visible()
    assert json.loads(page.locator("#version-json").text_content()) == inspected
    page.screenshot(path=str(output / f"version-readonly-{width}.png"), full_page=True)
    page.locator("#version-back").click()
    expect(version_row).to_be_visible()
    page.remove_listener("request", capture_view_request)
    assert not view_mutations, view_mutations
    assert page.request.get(base + "/demo/api/context").json() == saved_before_view
    expect(version_row.locator(".activate-version")).to_be_disabled()
    page.once("dialog", lambda dialog: dialog.accept())
    version_row.locator(".publish-version").click()
    expect(version_row).to_contain_text("Published")
    version_row.get_by_role("button", name="Use for queries", exact=True).click()
    expect(page.locator("#active-status")).to_contain_text(f"browser-{width}")
    expect(
        version_row.get_by_role("button", name="Active for queries", exact=True)
    ).to_be_disabled()
    if pack.entry.id == "power" and width == 1440:
        version_row.locator(".version-comparison > summary").click()
        version_row.locator(".version-comparison select").select_option("starter")
        version_row.get_by_role("button", name="Compare", exact=True).click()
        expect(version_row.locator(".version-comparison-result")).to_contain_text("record_count")
        expect(version_row.locator(".version-comparison-result")).to_contain_text("added")
        version_row.locator(".restore-version").click()
        expect(page.locator("#notice")).to_contain_text("Draft restored")
        restored = page.request.get(base + "/demo/api/context").json()
        assert restored["draft"]["validation"] is None
        assert restored["review"]["baseline_version"] == f"browser-{width}"
        assert restored["active_version"] == f"browser-{width}"
    assert (
        page.request.post(
            base + "/demo/api/example",
            data={
                "pack_id": pack.entry.id,
                "snapshot_sha256": pack.fingerprint,
                "session_id": previous["session_id"],
                "context_sha256": previous["context_sha256"],
                "example_id": previous["examples"][0]["id"],
            },
        ).status
        == 409
    )
    page.reload(wait_until="networkidle")
    expect(page.locator("#active-status")).to_contain_text(f"browser-{width}")
    page.locator("#tab-review").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(
        path=str(output / f"{pack.entry.id}-builder-review-{width}.png"), full_page=True
    )
    # New edits invalidate draft evidence while the reviewed version remains active.
    page.locator("#tab-define").click()
    page.locator("#metric-description").fill("An edited draft awaiting another review")
    page.locator("#tab-review").click()
    expect(page.locator("#review")).to_be_disabled()
    page.locator("#edit-draft").click()
    page.locator("#save").click()
    expect(page.locator("#save")).to_be_disabled()
    page.goto(base + "/demo/query", wait_until="networkidle")
    expect(page.locator("#review-note")).to_contain_text(f"browser-{width}")
    page.locator("#legacy-query").evaluate("el => el.open = true")
    page.locator("#example").select_option("record_count")
    page.locator("#run").click()
    expect(page.locator("#result")).to_be_visible(timeout=30000)
    if pack.entry.id == "power":
        expect(page.locator("#result-table")).to_be_visible()
        assert page.locator("#result-table tbody tr").count() > 1
    else:
        assert int(page.locator("#value").inner_text().replace(",", "")) > 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(output / f"{pack.entry.id}-builder-query-{width}.png"), full_page=True)
