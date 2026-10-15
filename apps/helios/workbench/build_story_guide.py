"""Build a self-contained illustrated guide from captured local UI screenshots."""
from __future__ import annotations

import base64
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/walkthrough/semantic-builder"

STEPS = [
    ("01-query-awaiting-review", "Start with the business question", "Data query", [
        "Open http://localhost:8084/demo to follow along in your own workspace.",
        "Ask: What is the measured electricity consumption?",
        "Check the context status before running a query."],
     "The starter snapshot awaits review. Run example stays disabled until a reviewed context becomes active.",
     "You are defining a reusable metric for an energy analyst. Include valid, non-estimated readings only; report kWh."),
    ("02-inspect-source", "Inspect the actual source fields", "Semantic Studio → Source data", [
        "Open Semantic Studio, then select Source data.",
        "Select meter_readings and inspect its columns and sample rows.",
        "Find import_kwh, quality_status, is_estimated, and meter_id. Inspect meters to understand the source relationship."],
     "Typed fields and up to ten sample rows appear. The source relationship links readings to meters.",
     "The selected power pack has four tables. This walkthrough uses synthetic source data and the available reporting period."),
    ("03-attach-business-note", "Give the builder business evidence", "Context artifacts → Attach documentation to draft", [
        "Expand Attach documentation to draft and choose power-business-notes.md from this guide's folder.",
        "Enter table meters, column meter_id, and entity value SYN-M000.",
        "Select Attach to draft. Save any unsaved edits first."],
     "The saved revision increases. The document receives a content hash and a verified source-entity link.",
     "The note explains valid, non-estimated kWh. The link identifies an example meter; it does not filter the metric to that meter."),
    ("04-review-llm-candidate", "Generate a candidate, then inspect it", "Semantic Studio → Source data", [
        "Select Generate with LLM and wait for the candidate.",
        "Expand Provenance, Source evidence, Assumptions, and Warnings.",
        "Check the measured_import_kwh formula and its evidence before selecting Apply to draft."],
     "Provenance records OpenAI and gpt-4o. Generation alone leaves the draft unchanged; Apply to draft creates the next revision.",
     "GPT output can vary. Create evidence draft is the deterministic alternative. Extra suggested metrics require their own business review."),
    ("05-edit-on-canvas", "Inspect the semantic model visually", "Semantic Studio → Studio", [
        "Inspect the table chain: substations, feeders, meters, and meter_readings.",
        "Select measured_import_kwh in the object tree or canvas.",
        "Keep this walkthrough focused on that metric. Remove any unrelated generated suggestions from this draft."],
     "The inspector shows the selected metric. The canvas distinguishes source relationships from SQL-derived dependencies.",
     "Moving nodes changes the saved layout, not the semantic definition. Connections and metric edits change the draft."),
    ("06-enrich-metric", "Record business meaning and ownership", "Metric inspector → Business meaning and evidence", [
        "Expand Business meaning and evidence. Set Owner to Energy Analytics.",
        "Add Measured electricity consumption and Verified imported energy as separate synonym lines.",
        "Record valid readings as the inclusion rule and estimated readings as the exclusion rule. Save draft."],
     "Business metadata becomes part of the saved context. The metric retains kWh units and its conditional SUM expression.",
     "Descriptions explain rules. SQL must enforce them. This example uses CASE conditions; it needs no additional structured filters."),
    ("07-validation-needs-reference", "Understand the validation gate", "Validation & review", [
        "Select Validation & review, then Validate SQL.",
        "Inspect the message when independent reference SQL is missing.",
        "Return to Studio to supply the missing evidence."],
     "Validation requests reviewer-authored reference SQL. Complete-version approval remains blocked.",
     "This screenshot intentionally demonstrates the gate. Once you understand it, add the reference before your first validation."),
    ("08-independent-reference", "Write an independent calculation", "Studio → Metric inspector", [
        "Find Independent reference SQL for measured_import_kwh.",
        "Paste the reference query below, after checking its conditions against the business definition.",
        "Select Save draft."],
     "The reference uses WHERE conditions. The semantic expression uses CASE conditions; both represent the same chosen business rules.",
     "Keep the output alias measured_import_kwh. The reference must come from your business understanding, not an LLM-generated expected answer."),
    ("09-validation-passed", "Compare SQL results and relationship checks", "Validation & review", [
        "Select Validate SQL again.",
        "Compare compiled SQL, reference SQL, and both result sets.",
        "Check the relationship results for duplicate keys, null target keys, and unmatched rows."],
     "All checks pass for saved revision 4 in this capture. Both calculations return 8,547.282 kWh.",
     "Revision numbers can differ in your session. Agreement proves this sample reconciliation; the reviewer still confirms business meaning."),
    ("10-inspect-changes", "Review exactly what changed", "Validation & review → Definition review", [
        "Keep Starter definitions as the comparison baseline.",
        "Find measured_import_kwh and expand Before / after.",
        "Inspect highlighted metadata and SQL changes. Clear the filter before reviewing the remaining objects."],
     "The comparison highlights changed fields. This walkthrough has 24 review objects, including document evidence and ontology mappings.",
     "Inspect metrics, relationships, metadata, documents, and mappings. A technical pass does not approve these business decisions."),
    ("11-batch-review", "Approve an inspected group of objects", "Validation & review → Batch decision", [
        "Inspect the remaining objects, then clear Find objects to include them all.",
        "Select all matching, then Approve selected.",
        "Check eligible and blocked counts. Enter your reviewer name and note, confirm the checkbox, then confirm the decision."],
     "All selected eligible items receive decisions for the exact saved revision. Blocked items stay unresolved.",
     "Use Request changes when an item is unclear. These screenshots use an automation reviewer only in the separate synthetic walkthrough workspace."),
    ("12-approve-version", "Create an immutable reviewed version", "Semantic Hub", [
        "Open Semantic Hub after every required item is approved.",
        "Enter walkthrough-v1 as the version name, or another unused name.",
        "Enter your reviewer name and review note, confirm the checkbox, then select Approve whole version."],
     "The version freezes its definition, semantic model, validation evidence, review decisions, and context artifacts.",
     "The button stays disabled if validation is missing, outdated, or unsuccessful, or if required item decisions remain unresolved."),
    ("13-reviewed-unpublished", "Inspect the version before publication", "Semantic Hub → Version history", [
        "Find walkthrough-v1 in Version history.",
        "Select Inspect to examine its immutable context and validation evidence.",
        "Use Download context JSON if you need the complete reviewed package."],
     "The version is Reviewed · unpublished. Use for queries is still disabled.",
     "Approving a version does not publish it. The current query context remains unchanged."),
    ("14-published-and-active", "Publish, then activate deliberately", "Semantic Hub → Version history", [
        "Select Publish for walkthrough-v1 and confirm local publication.",
        "Check that the version now shows Published.",
        "Select Use for queries. Check that the button changes to Active for queries."],
     "The active context becomes walkthrough-v1. A newly opened query page receives this version and its context hash.",
     "Publication makes the version available locally. Activation chooses which published version the local query page uses."),
    ("15-version-artifacts", "Inspect the complete version package", "Context artifacts", [
        "Choose walkthrough-v1 in Inspect version.",
        "Select Inspect artifacts and expand semantic layer, metadata, ontology, documents, and quality.",
        "Check that the uploaded note, its entity link, and metric metadata belong to this version."],
     "The panel returns the frozen artifacts from the reviewed version. Draft inspection instead loads the latest saved draft.",
     "Ontology mappings remain structural proposals with separate review evidence. Documents remain supporting assertions, not automatically authoritative facts."),
    ("16-compare-version", "Compare a release with its baseline", "Semantic Hub → Version history", [
        "Choose walkthrough-v1 under Compare version.",
        "Choose Starter definitions under Baseline and select Compare versions.",
        "Expand the metric or another changed object to inspect its before/after fields."],
     "The version comparison identifies changes without modifying either version.",
     "Use the same controls to compare two reviewed versions when a later release exists."),
    ("17-query-result", "Run the approved metric", "Data query", [
        "Open Data query after activating the version.",
        "Confirm the active context is walkthrough-v1.",
        "Choose What is the measured electricity consumption? and select Run example."],
     "The result is 8,547.282 kWh for this synthetic source snapshot.",
     "The query page currently runs predefined reviewed metrics. GPT-4o generated the authoring proposal; it does not plan this query."),
    ("18-query-evidence", "Trace the answer to its definition", "Data query → Execution evidence", [
        "Expand Execution evidence below the result.",
        "Inspect the compiled SQL and its VALID/non-estimated conditions.",
        "Check the context version, source snapshot, SQL hash, and result hash."],
     "The displayed answer is tied to the active semantic context and the selected source snapshot.",
     "The business story is complete: a supported definition became a reviewed version and then a traceable result."),
    ("19-next-draft-active-version", "Start the next revision safely", "Semantic Hub → Create draft", [
        "Return to Semantic Hub and select Create draft on walkthrough-v1.",
        "Make the next business change in Studio and save it.",
        "Validate, review, approve a new version, publish, and activate when ready."],
     "Restoring creates a new draft revision and clears its validation. Queries continue using walkthrough-v1 until another published version is activated.",
     "The capture stops immediately after creating the new draft. It does not create or activate a second release."),
]


def main():
    reference = (OUT / "reference.sql").read_text()
    note = (OUT / "power-business-notes.md").read_text()
    cards, links = [], []
    for number, (image, title, location, actions, expected, explanation) in enumerate(STEPS, 1):
        image_path = OUT / "screenshots" / (image + ".png")
        data = base64.b64encode(image_path.read_bytes()).decode()
        links.append(f'<a href="#step-{number}"><span>{number:02}</span>{escape(title)}</a>')
        extra = ""
        if number == 8:
            extra = '<div class="codebox"><button class="copy" data-copy="reference">Copy SQL</button><pre id="reference">' + escape(reference) + '</pre></div>'
        if number == 3:
            extra = '<details><summary>Business note to upload</summary><div class="codebox"><button class="copy" data-copy="business-note">Copy note</button><pre id="business-note">' + escape(note) + '</pre></div></details>'
        cards.append(f'''<section class="step" id="step-{number}">
<div class="step-heading"><span class="number">{number:02}</span><div><p class="location">{escape(location)}</p><h2>{escape(title)}</h2></div></div>
<div class="step-body"><div class="instructions"><ol>{''.join('<li>'+escape(action)+'</li>' for action in actions)}</ol>
<div class="expected"><strong>What you should see</strong><p>{escape(expected)}</p></div><p class="explanation">{escape(explanation)}</p>{extra}</div>
<figure><button class="image-button" data-title="Step {number}: {escape(title)}" aria-label="Enlarge screenshot for step {number}"><img src="data:image/png;base64,{data}" alt="Actual local UI screenshot: {escape(title)}" loading="lazy"></button><figcaption>Actual local application · step {number:02} · click to enlarge</figcaption></figure></div>
</section>''')
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>From source data to a reviewed energy metric — Helios walkthrough</title>
<style>
:root{--blue:#2563eb;--ink:#1e293b;--muted:#52617a;--line:#dfe6f1;--soft:#eff6ff}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f5f7fb;color:var(--ink);font:15px/1.65 system-ui,-apple-system,sans-serif}a{color:var(--blue)}button{font:inherit;cursor:pointer}aside{position:fixed;inset:0 auto 0 0;width:266px;padding:24px 18px;background:#fff;border-right:1px solid var(--line);overflow:auto}.brand{font-size:18px;font-weight:800;color:#ff5a1f;letter-spacing:1px}.brand small{display:block;color:var(--muted);font-size:11px;letter-spacing:0}.toc{display:grid;gap:3px;margin-top:20px}.toc a{display:flex;gap:10px;padding:8px;border-radius:7px;color:var(--muted);font-size:12px;text-decoration:none}.toc a span{color:var(--blue);font-weight:700}.toc a:hover,.toc a.active{background:var(--soft);color:var(--blue)}main{margin-left:266px;padding:34px;max-width:1800px}h1{font-size:36px;line-height:1.18;max-width:800px;margin:8px 0 18px}h2{font-size:22px;line-height:1.3;margin:0}h3{font-size:16px}.kicker,.location{text-transform:uppercase;letter-spacing:1px;font-size:11px;font-weight:700;color:var(--muted)}.lead{max-width:900px;font-size:18px}.intro,.step,.resources{background:white;border:1px solid var(--line);border-radius:14px;padding:26px;margin-bottom:26px}.callout{padding:16px 18px;border-left:4px solid var(--blue);background:var(--soft);margin:18px 0}.callout p{margin:4px 0}.flow{white-space:pre-wrap;font:13px/1.7 ui-monospace,monospace;background:#f8fafc;padding:16px;border-radius:8px}.actions{display:flex;gap:10px;flex-wrap:wrap}.actions a,.print{display:inline-block;background:var(--blue);color:white;border:0;border-radius:7px;padding:10px 14px;text-decoration:none}.actions a.secondary{background:var(--soft);color:var(--blue)}.step{scroll-margin-top:20px}.step-heading{display:flex;align-items:center;gap:14px;margin-bottom:22px}.number{font-size:22px;color:var(--blue);background:var(--soft);padding:8px 12px;border-radius:10px;font-weight:750}.location{margin:0 0 4px}.step-body{display:grid;grid-template-columns:minmax(260px,30%) minmax(0,1fr);gap:24px;align-items:start}.instructions ol{padding-left:22px;margin:0}.instructions li{margin-bottom:12px}.expected{background:var(--soft);padding:14px;border-radius:8px;margin-top:16px;font-size:13px}.expected p{margin:5px 0 0}.explanation{font-size:13px;color:var(--muted)}figure{margin:0;min-width:0}.image-button{display:block;width:100%;padding:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#f8fafc;cursor:zoom-in}figure img{display:block;width:100%;height:auto}figcaption{font-size:11px;color:var(--muted);margin-top:7px}.codebox{position:relative;background:#f8fafc;border:1px solid var(--line);border-radius:8px;margin-top:12px;padding:12px}.codebox pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;margin-top:30px}.copy{position:absolute;right:8px;top:7px;border:1px solid var(--line);background:white;color:var(--blue);border-radius:4px;font-size:11px}.copy:focus-visible,a:focus-visible,button:focus-visible{outline:3px solid #93c5fd;outline-offset:2px}details{font-size:13px;margin:15px 0}summary{color:var(--blue);cursor:pointer}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid var(--line);text-align:left;padding:10px}dialog{width:min(1500px,96vw);max-height:96vh;padding:16px;border:1px solid var(--line);border-radius:12px}dialog::backdrop{background:#0f172acc}dialog img{width:100%;display:block}dialog header{display:flex;justify-content:space-between;gap:12px;align-items:center;position:sticky;top:0;background:white;padding:8px}dialog button{background:var(--blue);color:white;border:0;padding:7px 12px;border-radius:5px}.footer{color:var(--muted);font-size:12px}.progress{height:3px;background:var(--blue);position:fixed;top:0;left:0;width:0;z-index:5}
@media(max-width:1100px){aside{width:225px}main{margin-left:225px;padding:20px}.step-body{grid-template-columns:1fr}.intro,.step{padding:20px}h1{font-size:30px}}
@media(max-width:700px){aside{position:static;width:auto;border-bottom:1px solid var(--line)}.toc{max-height:160px;overflow:auto}main{margin:0;padding:14px}.step-body{gap:16px}.step{padding:16px}h1{font-size:27px}h2{font-size:20px}}
@page{size:A4 landscape;margin:12mm}
@media print{body{background:white;font-size:11px}aside,.progress,.actions,.copy,.print,dialog{display:none!important}main{margin:0;padding:0;max-width:none}.intro,.step,.resources{border:0;border-radius:0;margin:0;padding:0}.intro{break-after:page}.step{break-before:page;break-inside:avoid}.step-heading{margin-bottom:10px}.step-body{grid-template-columns:29% minmax(0,1fr);gap:16px}.instructions li{margin-bottom:8px}.step img{width:100%;max-height:151mm;object-fit:contain;object-position:top}.step .explanation,.expected{font-size:10px}.expected{padding:8px;margin-top:8px}figcaption{font-size:9px}.number{font-size:17px}h2{font-size:18px}.location{font-size:9px}.codebox pre{margin:0;font-size:9px}.resources{break-before:page}a{color:inherit;text-decoration:none}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style></head><body><div class="progress"></div><aside><div class="brand">CLOUDERA<small>Semantic builder · illustrated walkthrough</small></div><nav class="toc" aria-label="Walkthrough steps">__LINKS__</nav></aside><main>
<section class="intro"><p class="kicker">Captured from the local application · 12 October 2026</p><h1>From source data to a reviewed energy metric</h1><p class="lead">An energy analyst needs one reusable answer: <strong>What is the measured electricity consumption?</strong> Build its meaning, verify its calculation, then release a version that queries can trust.</p>
<div class="callout"><p><strong>Target definition:</strong> imported kWh from VALID, non-estimated readings, across the available sample period.</p><p><strong>Captured result:</strong> 8,547.282 kWh · <strong>Release:</strong> walkthrough-v1 · <strong>Runtime:</strong> typed local DuckDB.</p></div>
<pre class="flow">Source tables + business note → GPT-4o candidate → editable Studio draft
                                                          ↓
Query result ← activate ← publish ← reviewed version ← SQL validation + item review</pre>
<p><strong>Follow along:</strong> use your existing instance on port 8084. Screenshots use a separate instance on port 8085 with the same application.</p><p>The walkthrough's approval records use an explicit automation identity for synthetic demonstration only. Your original draft and versions remain unchanged.</p>
<div class="actions"><a href="http://localhost:8084/demo/context" target="_blank" rel="noopener">Open your Studio</a><a class="secondary" href="http://localhost:8085/demo" target="_blank" rel="noopener">Inspect the completed demo</a><button class="print" onclick="window.print()">Print / save PDF</button></div>
<h3>Where each task belongs</h3><table><tr><th>Section</th><th>Responsibility</th></tr><tr><td>Semantic Studio</td><td>Inspect sources, generate and edit drafts, validate SQL, and review individual changes.</td></tr><tr><td>Semantic Hub</td><td>Approve complete versions, compare, publish, inspect artifacts, and choose the active version.</td></tr><tr><td>Data query</td><td>Execute predefined reviewed metrics and inspect their result and evidence.</td></tr></table>
<p class="footer">This guide contains 19 actual screenshots. Images are embedded, so this HTML file works offline. Local app links require a running instance.</p></section>
__CARDS__
<section class="resources"><h2>Files and checkpoints</h2><p>The guide folder includes the exact demonstration inputs and a published consumer package.</p><ul><li><a href="power-business-notes.md">power-business-notes.md</a> — upload this business note.</li><li><a href="reference.sql">reference.sql</a> — independent calculation for the selected metric.</li><li><a href="walkthrough-v1.consumer.json">walkthrough-v1.consumer.json</a> — exported manifest, Ossie document, context, and artifact bundle.</li><li><a href="screenshots/">screenshots/</a> — all original captures.</li></ul><h3>If a control is disabled</h3><table><tr><th>Control</th><th>What to check</th></tr><tr><td>Generate with LLM / Apply to draft</td><td>Save pending edits. Confirm the provider is configured. Apply a candidate generated for the current revision.</td></tr><tr><td>Validate SQL</td><td>Save the draft first. Every metric needs independent reference SQL before validation can pass.</td></tr><tr><td>Approve whole version</td><td>Validate the current revision and approve every required review object. Clear review filters to find remaining objects.</td></tr><tr><td>Use for queries</td><td>Publish the reviewed version first.</td></tr><tr><td>Run example</td><td>Activate a published version and reload Data query to obtain its current binding.</td></tr></table><p>Typing a descriptive inclusion rule does not create an executable filter. Inspect the metric expression or structured filters.</p><p>Only one linked note is supplied in this power demonstration. Source documents and ontology mappings retain explicit provenance and review status.</p><p>Export is a handoff package. Consumer applications still need their integration adapters; local publication does not deploy to another application.</p></section>
</main><dialog id="lightbox"><header><strong id="lightbox-title"></strong><button id="close-lightbox">Close</button></header><img id="lightbox-image" alt=""></dialog><script>
const box=document.getElementById('lightbox');document.querySelectorAll('.image-button').forEach(button=>button.onclick=()=>{const image=button.querySelector('img');document.getElementById('lightbox-image').src=image.src;document.getElementById('lightbox-image').alt=image.alt;document.getElementById('lightbox-title').textContent=button.dataset.title;box.showModal()});document.getElementById('close-lightbox').onclick=()=>box.close();box.addEventListener('click',event=>{if(event.target===box)box.close()});document.querySelectorAll('.copy').forEach(button=>button.onclick=async()=>{const text=document.getElementById(button.dataset.copy).textContent;try{await navigator.clipboard.writeText(text);button.textContent='Copied'}catch{const range=document.createRange();range.selectNodeContents(document.getElementById(button.dataset.copy));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);button.textContent='Selected — copy now'}});const links=[...document.querySelectorAll('.toc a')];const observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){links.forEach(link=>link.classList.toggle('active',link.hash==='#'+entry.target.id))}},{rootMargin:'-10% 0px -65% 0px'});document.querySelectorAll('.step').forEach(step=>observer.observe(step));addEventListener('scroll',()=>{const total=document.documentElement.scrollHeight-innerHeight;document.querySelector('.progress').style.width=(total>0?scrollY/total*100:0)+'%'});
</script></body></html>'''
    html = html.replace("__LINKS__", "".join(links)).replace("__CARDS__", "".join(cards))
    (OUT / "index.html").write_text(html)
    (OUT / "storyline.json").write_text(json.dumps([
        {"step": i, "screenshot": row[0]+".png", "title": row[1], "location": row[2],
         "actions": row[3], "expected": row[4], "explanation": row[5]}
        for i, row in enumerate(STEPS, 1)
    ], indent=2) + "\n")
    print(f"Built {OUT / 'index.html'} with {len(STEPS)} embedded screenshots")


if __name__ == "__main__":
    main()
