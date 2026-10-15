"""Capture an instructional workflow in a dedicated local sample workspace.

Run each phase once, in order. Release actions use an explicit demonstration
reviewer. Never point this script at an operator workspace.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = """SELECT SUM(import_kwh) AS measured_import_kwh
FROM meter_readings
WHERE quality_status = 'VALID'
  AND is_estimated = 'false'"""
NOTE = """# Measured electricity consumption

This document describes a synthetic demonstration dataset.
Count imported energy only when quality_status is VALID and is_estimated is false.
The unit is kWh. Reporting dates use Asia/Singapore. This demonstration has no date filter.
Owner: Energy Analytics. Meter SYN-M000 is an example source entity.
This note records intended meaning; the SQL expression must enforce the conditions.
"""
VERSION = "walkthrough-v1"
REVIEWER = "Walkthrough automation — synthetic sample only"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8085")
    parser.add_argument("--phase", choices=["author", "release", "query"], required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/walkthrough/semantic-builder")
    args = parser.parse_args()
    if args.base != "http://127.0.0.1:8085":
        raise SystemExit("Use the dedicated walkthrough instance on port 8085")
    shots = args.output / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    (args.output / "power-business-notes.md").write_text(NOTE)
    (args.output / "reference.sql").write_text(REFERENCE + ";\n")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.set_default_timeout(15000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def state():
            response = page.request.get(args.base + "/demo/api/context")
            assert response.ok
            return response.json()

        def capture(name, target=None):
            if target:
                page.locator(target).scroll_into_view_if_needed()
            else:
                page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=str(shots / f"{name}.png"))
            assert not errors, errors
            print("Captured " + name, flush=True)

        def save():
            page.locator("#save").click()
            expect(page.locator("#save")).to_be_disabled()
            expect(page.locator("#notice")).to_contain_text("saved", timeout=30000)

        try:
            if args.phase == "author":
                assert state()["draft"]["revision"] == 0, "Author phase needs a fresh walkthrough workspace"
                page.goto(args.base + "/demo/query", wait_until="networkidle")
                expect(page.locator("#run")).to_be_disabled()
                capture("01-query-awaiting-review")
                page.get_by_role("link", name="Semantic Studio", exact=True).click()
                expect(page.locator("#pack-title")).to_have_text("SP Group power prototype")
                page.locator("#tab-source").click()
                page.locator('[data-table="meter_readings"]').click()
                expect(page.locator("#table-name")).to_have_text("meter_readings")
                capture("02-inspect-source", "#table-detail")
                page.locator("#tab-source").click()
                page.locator("#local-document-notes").evaluate("element => element.open = true")
                page.locator("#document-add").click()
                page.locator("#document-file").set_input_files(str(args.output / "power-business-notes.md"))
                page.locator("#document-link-options summary").click()
                for field, value in {"table": "meters", "column": "meter_id", "value": "SYN-M000"}.items():
                    page.locator("#document-" + field).fill(value)
                capture("03-attach-business-note", "#document-form")
                page.locator("#document-upload").click()
                expect(page.locator("#notice")).to_contain_text("Document added", timeout=30000)
                page.locator("#propose-llm").click()
                expect(page.locator("#proposal-apply")).to_be_enabled(timeout=180000)
                page.locator("#proposal-preview details").filter(has=page.get_by_text("Provenance", exact=True)).locator("summary").click()
                capture("04-review-llm-candidate", "#proposal-preview")
                page.locator("#proposal-apply").click()
                expect(page.locator("#notice")).to_contain_text("Candidate applied", timeout=30000)
                capture("05-edit-on-canvas")
                # The story has one business question. Extra suggestions remain
                # visible in candidate history, but do not enter this release.
                for metric in state()["draft"]["definition"]["metrics"]:
                    if metric["name"] != "measured_import_kwh":
                        page.locator("#metric-list").get_by_role("button", name=metric["name"], exact=True).click()
                        page.locator("#remove-metric").click()
                page.locator("#metric-list").get_by_role("button", name="measured_import_kwh", exact=True).click()
                page.locator(".semantic-fields").filter(has=page.locator("#metric-owner")).locator("summary").click()
                for field, value in {
                    "owner": "Energy Analytics",
                    "synonyms": "Measured electricity consumption\nVerified imported energy",
                    "example_questions": "What is the measured electricity consumption?",
                    "inclusion_rules": "Include readings with quality_status = VALID.",
                    "exclusion_rules": "Exclude estimated readings.",
                    "reference_sql": "",
                }.items():
                    page.locator("#metric-" + field).fill(value)
                capture("06-enrich-metric", "#metric-owner")
                save()
                page.locator("#tab-validate").click()
                page.locator("#validate").click()
                expect(page.locator("#validation-results")).to_contain_text("Supply reviewer-authored reference SQL", timeout=30000)
                capture("07-validation-needs-reference", "#validation-results")
                page.locator("#tab-define").click()
                page.locator("#metric-reference_sql").fill(REFERENCE)
                capture("08-independent-reference", "#metric-reference_sql")
                save()
                page.locator("#tab-validate").click()
                page.locator("#validate").click()
                expect(page.locator("#validation-status")).to_have_text("All checks passed for this saved draft.", timeout=30000)
                capture("09-validation-passed", "#validation-results")
                page.locator("#review-filter").fill("measured_import_kwh")
                page.locator("#review-items summary").first.click()
                capture("10-inspect-changes", ".review-workspace")

            elif args.phase == "release":
                assert state()["draft"]["validation"]["passed"]
                assert not state()["versions"], "Release phase must run once"
                page.goto(args.base + "/demo/context#validate", wait_until="networkidle")
                page.locator("#select-all").click()
                page.locator("#approve-selected").click()
                expect(page.locator("#batch-dialog")).to_be_visible()
                page.locator("#batch-reviewer").fill(REVIEWER)
                page.locator("#batch-note").fill("Demonstration only: checked source keys, business rules, document links, ontology mappings, and SQL agreement.")
                page.locator("#batch-confirmed").check()
                capture("11-batch-review")
                page.locator("#batch-submit").click()
                expect(page.locator("#notice")).to_contain_text("decisions recorded", timeout=30000)
                assert all(item["status"] == "approved" for item in state()["review"]["items"])
                page.locator("#tab-review").click()
                page.locator("#version").fill(VERSION)
                page.locator("#reviewer").fill(REVIEWER)
                page.locator("#review-note").fill("Synthetic walkthrough release. Valid, non-estimated kWh reconciled against an independently written WHERE query.")
                page.locator("#confirmed").check()
                capture("12-approve-version", "#review-form")
                page.locator("#review").click()
                expect(page.locator("#versions")).to_contain_text(VERSION, timeout=30000)
                row = page.locator(".version-row").filter(has=page.get_by_text(VERSION, exact=True))
                capture("13-reviewed-unpublished", "#versions")
                expect(row.locator(".activate-version")).to_be_disabled()
                page.once("dialog", lambda dialog: dialog.accept())
                row.get_by_role("button", name="Publish", exact=True).click()
                expect(row).to_contain_text("Published", timeout=30000)
                row.get_by_role("button", name="Use for queries", exact=True).click()
                expect(page.locator("#active-status")).to_contain_text(VERSION, timeout=30000)
                capture("14-published-and-active", "#versions")
                page.locator("#artifact-version").select_option(VERSION)
                page.locator("#artifact-refresh").click()
                expect(page.locator("#notice")).to_have_text("Context artifacts loaded.", timeout=30000)
                page.locator("#artifact-content > details").filter(has=page.get_by_text("documents", exact=True)).locator("summary").click()
                capture("15-version-artifacts", "#artifact-content")
                response = page.request.get(args.base + "/demo/api/context/export?version=" + VERSION)
                assert response.ok
                (args.output / "walkthrough-v1.consumer.json").write_text(json.dumps(response.json(), indent=2) + "\n")
                page.locator("#compare-version").select_option(VERSION)
                page.locator("#compare-baseline").select_option("starter")
                page.locator("#compare").click()
                expect(page.locator("#comparison")).to_contain_text("compared with starter")
                page.locator("#comparison details").filter(has=page.locator("summary", has_text="measured_import_kwh")).first.locator("summary").click()
                capture("16-compare-version", "#comparison")

            else:
                page.goto(args.base + "/demo/query", wait_until="networkidle")
                expect(page.locator("#query-context")).to_contain_text(VERSION)
                page.locator("#run").click()
                expect(page.locator("#result")).to_be_visible(timeout=30000)
                expect(page.locator("#value")).to_have_text("8,547.282")
                capture("17-query-result", "#result")
                page.locator("#result summary").click()
                capture("18-query-evidence", "#evidence")
                page.goto(args.base + "/demo/context#hub", wait_until="networkidle")
                row = page.locator(".version-row").filter(has=page.get_by_text(VERSION, exact=True))
                row.get_by_role("button", name="Create draft", exact=True).click()
                expect(page.locator("#notice")).to_contain_text("Draft restored", timeout=30000)
                expect(page.locator("#active-status")).to_contain_text(VERSION)
                assert state()["draft"]["validation"] is None
                capture("19-next-draft-active-version")
            (args.output / f"{args.phase}-evidence.json").write_text(json.dumps({
                "phase": args.phase, "base": args.base, "review_scope": "synthetic walkthrough only",
                "state": state(), "browser_errors": errors,
            }, indent=2) + "\n")
        except Exception:
            page.screenshot(path=str(shots / "capture-error.png"))
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
