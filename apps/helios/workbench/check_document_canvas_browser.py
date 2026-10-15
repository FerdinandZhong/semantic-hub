"""Check document → canvas → review navigation without modifying saved drafts."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import expect, sync_playwright


def check_document_journey(page, doc, output=None, prefix="document"):
    filename = doc["filename"].split("/")[-1]
    object_id = ("source-document:" if doc["origin"] == "serving_document" else "document:") + doc["id"]
    before = page.evaluate("JSON.stringify(contextStudio.getState().workspace)")
    page.locator("#tab-define").click()
    expect(page.locator(".canvas-node.document_group")).to_have_count(1)
    expect(page.locator(".canvas-node.document")).to_have_count(0)
    page.locator(".canvas-node.document_group").click()
    expect(page.locator("#source-inspector")).to_contain_text("Supporting documents")
    page.locator("#source-inspector button").filter(has_text=filename).first.click()
    expect(page.locator(".canvas-node.document")).to_have_count(1)
    expect(page.locator(".canvas-node.document")).to_have_attribute("data-node-id", object_id)
    expect(page.locator("#source-inspector .document-text")).to_have_text(doc["content"])
    expect(page.locator(".canvas-edge.evidence")).to_have_count(len(doc["entity_links"]))
    for link in doc["entity_links"]:
        expect(page.locator("#source-inspector")).to_contain_text(f"{link['table']}.{link['column']} = {link['value']}")
    if not doc["entity_links"]:
        expect(page.locator("#source-inspector")).to_contain_text("Model-wide context")
    if output:
        page.locator(".studio-layout").screenshot(path=str(output / f"{prefix}-canvas.png"))
    page.get_by_role("button", name="Review this document", exact=True).filter(visible=True).click()
    row = page.locator("#review-items tr").filter(has=page.get_by_role("button", name="Open in canvas", exact=True)).first
    expect(row).to_contain_text("document")
    row.get_by_role("button", name="Open in canvas", exact=True).click()
    expect(page.locator("#source-inspector .document-text")).to_have_text(doc["content"])
    page.get_by_role("button", name="Open source document", exact=True).click()
    expect(page.locator("#document-detail .document-text")).to_have_text(doc["content"])
    page.locator("#document-detail").get_by_role("button", name="Show in canvas", exact=True).click()
    expect(page.locator(".canvas-node.document")).to_have_count(1)
    page.get_by_role("button", name="View options", exact=True).click()
    page.get_by_role("button", name="Show all", exact=True).click()
    expect(page.locator(".canvas-node.document")).to_have_count(0)
    expect(page.locator(".canvas-node.document_group")).to_have_count(1)
    page.get_by_role("button", name="View options", exact=True).click()
    assert page.evaluate("JSON.stringify(contextStudio.getState().workspace)") == before
    assert not page.evaluate("contextStudio.getState().dirty")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8084")
    parser.add_argument("--output", type=Path, default=Path("/tmp/helios-document-canvas"))
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for source in ("finance", "manufacturing", "pharma", "power"):
            for width in (1440, 390):
                page = browser.new_page(viewport={"width": width, "height": 1000})
                errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"{args.base}/demo/context?source={source}", wait_until="networkidle")
                docs = page.request.get(f"{args.base}/demo/api/context/documents?source={source}").json()["items"]
                if docs:
                    check_document_journey(page, docs[0], args.output, f"{source}-{width}")
                else:
                    expect(page.locator(".canvas-node.document_group")).to_have_count(0)
                    expect(page.locator(".canvas-node.document")).to_have_count(0)
                assert not errors, errors
                results.append({"source": source, "width": width, "documents": len(docs), "status": "passed"})
                page.close()
        browser.close()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
