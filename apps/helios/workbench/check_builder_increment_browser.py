"""Verify incremental builder features across four packs and two screen sizes.

All review receipts and authored drafts live in a temporary test directory.
This check does not approve, publish, or activate a builder version.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))


def unique_link(pack):
    for table in pack.tables:
        rows = list(csv.DictReader(io.StringIO(table.csv_bytes.decode("utf-8"))))
        if not rows:
            continue
        for column in rows[0]:
            values = [row[column] for row in rows]
            if all(values) and len(set(values)) == len(values):
                return {"table": table.name, "column": column, "value": values[0]}
    raise AssertionError(f"No unique entity key in {pack.entry.id}")


def check_increment(page, base, pack, width, output):
    from playwright.sync_api import expect

    def saved():
        response = page.request.get(base + "/demo/api/context")
        assert response.ok, response.text()
        return response.json()

    def screenshot(name):
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
        page.screenshot(path=str(output / f"{pack.entry.id}-{width}-{name}.png"), full_page=True)

    page.goto(base + "/demo/context", wait_until="networkidle")
    expect(page.locator("#studio-canvas .canvas-node").first).to_be_visible()
    initial = saved()
    revision = initial["draft"]["revision"]
    page.locator("#tab-source").click()
    page.locator("#propose-evidence").click()
    expect(page.locator("#proposal-preview")).to_be_visible()
    expect(page.locator("#proposal-apply")).to_be_enabled(timeout=30000)
    assert saved()["draft"]["revision"] == revision, "Generation must not modify the draft"
    expect(page.locator("#proposal-preview")).to_contain_text("Provenance")
    expect(page.locator("#proposal-preview")).to_contain_text("Assumptions")
    expect(page.locator("#proposal-preview")).to_contain_text("Warnings")
    screenshot("proposal")
    page.locator("#proposal-apply").click()
    expect(page.locator("#notice")).to_contain_text("Candidate applied", timeout=30000)
    applied = saved()
    assert applied["draft"]["revision"] == revision + 1
    assert applied["draft"]["validation"] is None
    assert not applied["versions"]
    assert all(item["status"] != "approved" for item in applied["review"]["items"])

    page.locator('[data-inspector="metric"]').click()
    page.locator("details.semantic-fields").filter(has=page.locator("#metric-synonyms")).locator("summary").click()
    synonyms = [f"browser meaning {width}", "verified test synonym"]
    page.locator("#metric-synonyms").fill("\n".join(synonyms))
    page.locator("#metric-example_questions").fill("What does this metric measure?")
    page.locator("#metric-owner").fill("browser-test-only")
    page.locator("#metric-inclusion_rules").fill("Use source records from the selected snapshot")
    page.locator("#metric-exclusion_rules").fill("Exclude no additional records")
    page.locator("#metric-assumptions").fill("Business definitions require human confirmation")
    page.locator("#metric-rationale").fill("Browser acceptance test metadata")
    page.locator("#metric-confidence").fill("0.75")
    metric_name = page.locator("#metric-name").input_value()
    page.locator("#tab-source").click()
    expect(page.locator("#propose-evidence")).to_be_disabled()
    expect(page.locator("#proposal-apply")).to_be_disabled()
    expect(page.locator("#proposal-status")).to_contain_text("unsaved changes")
    page.locator("#columns input").first.fill("Browser-tested source identifier meaning")
    page.locator("#save").click()
    expect(page.locator("#notice")).to_contain_text("saved", timeout=30000)
    metadata = saved()
    metric = next(m for m in metadata["draft"]["definition"]["metrics"] if m["name"] == metric_name)
    assert metric["synonyms"] == synonyms
    assert metric["owner"] == "browser-test-only"
    assert metric["confidence"] == 0.75
    assert "Browser-tested source identifier meaning" in metadata["draft"]["definition"]["field_meanings"].values()
    expect(page.locator("#proposal-apply")).to_be_disabled()  # Candidate revision is stale.
    page.reload(wait_until="networkidle")
    page.locator("#tab-define").click()
    page.locator('[data-inspector="metric"]').click()
    assert page.locator("#metric-synonyms").input_value() == "\n".join(synonyms)
    screenshot("metadata")

    link = unique_link(pack)
    page.locator("#tab-source").click()
    page.locator("#local-document-notes").evaluate("element => element.open = true")
    page.locator("#document-add").click()
    page.locator("#document-file").set_input_files({"name":"unsupported.pdf","mimeType":"application/pdf","buffer":b"Not a supported document"})
    expect(page.locator("#document-file-status")).to_contain_text("not supported")
    expect(page.locator("#document-upload")).to_be_disabled()
    filename = f"browser-context-{width}.md"
    content = f"# Browser context\nEntity {link['value']} requires human review.\n<script>window.documentPreviewExecuted=true</script>\n"
    page.locator("#document-file").set_input_files({"name": filename, "mimeType": "text/markdown", "buffer": content.encode()})
    page.locator("#document-link-options summary").click()
    for key in ("table", "column", "value"):
        page.locator("#document-" + key).fill(link[key])
    document_revision = saved()["draft"]["revision"]
    page.locator("#document-upload").click()
    expect(page.locator("#notice")).to_contain_text("Document added", timeout=30000)
    attached = saved()
    assert attached["draft"]["revision"] == document_revision + 1
    attachment = attached["draft"]["definition"]["document_attachments"][-1]
    assert attachment["filename"] == filename
    assert attachment["entity_links"] == [link]
    expect(page.locator("#document-detail")).to_contain_text(filename)
    expect(page.locator("#document-detail .document-text")).to_have_text(content)
    expect(page.locator("#document-detail")).to_contain_text("Pending review")
    expect(page.locator("#document-detail")).to_contain_text(link['value'])
    assert not page.evaluate('Boolean(window.documentPreviewExecuted)')
    screenshot("documents")
    from check_document_canvas_browser import check_document_journey
    document = next(doc for doc in page.request.get(base + "/demo/api/context/documents").json()["items"] if doc["filename"] == filename)
    check_document_journey(page, document, output, f"{pack.entry.id}-{width}-uploaded")
    page.locator("#tab-source").click()
    page.locator("#documents-review").click()
    expect(page.locator("#review-filter")).to_have_value("document")
    page.locator("#artifact-refresh").click()
    expect(page.locator("#notice")).to_have_text("Context artifacts loaded.", timeout=30000)
    for label in ("semantic layer", "metadata", "ontology", "documents", "quality"):
        expect(page.locator("#artifact-content > details > summary").filter(has_text=label).first).to_be_visible()
    artifacts = page.request.get(base + "/demo/api/context/artifacts?version=draft")
    assert artifacts.ok, artifacts.text()
    bundle = artifacts.json()
    assert all(key in bundle for key in ("semantic_layer", "metadata", "ontology", "documents", "quality"))
    assert any(doc["filename"] == filename and doc["content"] == content for doc in bundle["documents"])
    assert any(m["synonyms"] == synonyms for m in bundle["metadata"]["metrics"])
    screenshot("artifacts")
    if pack.entry.id == "power":
        # Model-wide context must not acquire a fabricated source record edge.
        page.locator("#tab-source").click()
        page.locator("#local-document-notes").evaluate("element => element.open = true")
        page.locator("#document-add").click()
        page.locator("#document-file").set_input_files({"name": "general-context.md", "mimeType": "text/markdown", "buffer": b"General business context without a record link."})
        page.locator("#document-upload").click()
        expect(page.locator("#notice")).to_contain_text("Document added", timeout=30000)
        general = next(doc for doc in page.request.get(base + "/demo/api/context/documents").json()["items"] if doc["filename"] == "general-context.md")
        assert general["entity_links"] == []
        check_document_journey(page, general, output, f"{pack.entry.id}-{width}-model-wide")
    assert not saved()["versions"], "This check must not approve a version"
    return {"pack": pack.entry.id, "width": width, "status": "passed", "draft_revision": saved()["draft"]["revision"], "document": filename}


def main():
    from playwright.sync_api import sync_playwright
    from helios_core.demo.registry import PackRegistry
    from helios_core.demo.runtime import review_pack

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/helios-builder-increment-browser"))
    parser.add_argument("--pack", choices=["finance", "manufacturing", "pharma", "power"])
    parser.add_argument("--preview-base", help="Capture the documents section on an existing instance without edits")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    registry = PackRegistry(ROOT / "apps/helios/demo-packs.json", ROOT / "apps/helios-ds-generation/fixtures/sectors/v1")
    if args.preview_base:
        from playwright.sync_api import expect
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for sector in ([args.pack] if args.pack else registry.entries):
                for width,height in ((1440,1000),(390,844)):
                    page=browser.new_page(viewport={'width':width,'height':height})
                    errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(args.preview_base+'/demo/context?source='+sector+'#source',wait_until='networkidle')
                    expect(page.locator('#documents-status')).to_contain_text('from source')
                    expect(page.locator('#documents-error')).not_to_be_visible()
                    expect(page.locator('#version-evidence')).not_to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.locator('#source-documents').screenshot(path=str(args.output/f'{sector}-{width}-documents.png'))
                    page.locator("#local-document-notes").evaluate("element => element.open = true")
                    page.locator('#document-add').click()
                    expect(page.locator('#document-form')).to_be_visible()
                    page.locator('#source-documents').screenshot(path=str(args.output/f'{sector}-{width}-add-document.png'))
                    assert not errors, errors
                    page.close()
            browser.close()
        print('PASS: read-only document previews')
        return
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="helios-builder-increment-") as temp, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for sector in registry.entries:
                if args.pack and sector != args.pack:
                    continue
                pack = registry.load(sector)
                for width, height in ((1440, 1000), (390, 844)):
                    state = Path(temp) / f"{sector}-{width}"
                    review_pack(pack, state, "automated-browser-test-only")
                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        port = sock.getsockname()[1]
                    base = f"http://127.0.0.1:{port}"
                    log_path = args.output / f"{sector}-{width}.log"
                    with log_path.open("w") as log:
                        process = subprocess.Popen([sys.executable, str(ROOT / "start_demo.py"), "--dataset", sector, "--state-dir", str(state), "--port", str(port)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "PYSTOW_HOME": str(state / "pystow"), "HELIOS_LLM_PROVIDER": "none"})
                        page = None
                        try:
                            deadline = time.monotonic() + 45
                            while True:
                                if process.poll() is not None:
                                    raise RuntimeError(f"Console exited; inspect {log_path}")
                                try:
                                    with urllib.request.urlopen(base + "/demo/api/config", timeout=1) as response:
                                        config = json.load(response)
                                    assert config["pack_id"] == sector
                                    break
                                except (OSError, urllib.error.URLError):
                                    if time.monotonic() > deadline:
                                        raise RuntimeError(f"Console startup timed out; inspect {log_path}")
                                    time.sleep(0.2)
                            page = browser.new_page(viewport={"width": width, "height": height})
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            result = check_increment(page, base, pack, width, args.output)
                            assert not errors, errors
                            result["javascript_errors"] = errors
                            outcomes.append(result)
                            (args.output / "results.json").write_text(json.dumps(outcomes, indent=2) + "\n")
                            print(json.dumps(result), flush=True)
                        finally:
                            if page:
                                page.close()
                            process.terminate()
                            try:
                                process.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=5)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
