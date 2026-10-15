"""Generate real LLM candidates from serving evidence; never approve them.

The credential is read directly into memory. Reports contain synthetic source
metadata and generated artifacts, but never provider credentials.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))


def run_pack(sector, credential, output, state, model, attach_sample=False):
    from helios_core.demo.builder_artifacts import BuilderArtifacts
    from helios_core.demo.context import ContextDefinition, ContextWorkspace
    from helios_core.demo.local import LocalPackEngine
    from helios_core.demo.proposals import ProposalWorkspace
    from helios_core.demo.registry import PackRegistry
    from helios_core.llm import LLMClient
    from helios_core.ossie import SemanticModel

    registry = PackRegistry(ROOT / "apps/helios/demo-packs.json", ROOT / "apps/helios-ds-generation/fixtures/sectors/v1")
    pack = registry.load(sector)
    workspace = ContextWorkspace(pack, state)
    revision = 0
    if attach_sample:
        import csv
        import io
        for table in pack.tables:
            rows = list(csv.DictReader(io.StringIO(table.csv_bytes.decode())))
            keys = [column for column in rows[0] if all(row[column] for row in rows)
                    and len({row[column] for row in rows}) == len(rows)] if rows else []
            if not keys:
                continue
            row = rows[0]
            link = {'table': table.name, 'column': keys[0], 'value': row[keys[0]]}
            content = (f"Synthetic authoring assessment note for {table.name}: {row[keys[0]]}. "
                       "An operator must confirm the reporting period and source meaning. "
                       "This note does not change declared metric formulas or certify source facts.")
            attachment = BuilderArtifacts(workspace).attach('authoring-assessment.md', content, [link])
            definition = workspace.seed() | {'document_attachments': [attachment]}
            workspace.save(0, ContextDefinition.model_validate(definition))
            revision = 1
            break
        if revision != 1:
            raise RuntimeError('No unique non-null source column for the attachment test')
    llm = LLMClient("openai", model, credential, "https://api.openai.com/v1", timeout=60)
    started = time.monotonic()
    report = {"pack": sector, "provider": "openai", "model": model,
              "scope": "live proposal from synthetic serving evidence; not human-approved",
              "source_documents": len(pack.documents), "metrics": []}
    try:
        proposal = ProposalWorkspace(workspace).generate(revision, "llm", llm)
        (output / f"{sector}-proposal.json").write_text(json.dumps(proposal, indent=2))
        definition = ContextDefinition.model_validate(proposal["definition"])
        document = workspace.build_model(definition)
        artifacts = BuilderArtifacts(workspace).bundle(definition, document)
        (output / f"{sector}-artifacts.json").write_text(json.dumps(artifacts, indent=2))
        engine = LocalPackEngine(pack)
        try:
            for metric in definition.metrics:
                sql = workspace.compile_metric(SemanticModel(document), metric).sql
                result = engine.query(sql, limit=200)
                report["metrics"].append({"name": metric.name, "description": metric.description,
                    "unit": metric.unit, "grain": metric.grain, "time_rule": metric.time_rule,
                    "expression": metric.expression, "sql": sql, "rows": result.rows,
                    "reference_sql_empty": not metric.reference_sql,
                    "assumptions": metric.assumptions, "ontology_concepts": metric.ontology_concepts})
        finally:
            engine.close()
        report.update(status="generated_and_executable", proposal_warnings=proposal["warnings"],
            artifact_warnings=artifacts["quality"]["warnings"],
            field_count=len(artifacts["metadata"]["fields"]),
            draft_unchanged=workspace.view()["draft"]["revision"] == revision,
            attached_sample=attach_sample,
            document_coverage=proposal['evidence'].get('document_coverage'),
            business_review="required; SQL execution is not business correctness")
    except Exception as error:
        # Provider errors can contain sensitive headers/body fragments. Persist only
        # their types; locally generated contract errors are safe and actionable.
        report.update(status="failed", error_type=type(error).__name__)
        if type(error).__module__.startswith(("helios_core.demo", "pydantic", "sqlglot")):
            report["error"] = str(error)[:1500]
    report.update(llm_calls=llm.calls, elapsed_seconds=round(time.monotonic() - started, 2))
    (output / f"{sector}-assessment.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--pack", choices=["finance", "manufacturing", "pharma", "power"])
    parser.add_argument("--attach-sample", action="store_true", help="Attach a linked synthetic review note before proposing")
    parser.add_argument("--output", type=Path, default=Path("/tmp/helios-builder-live"))
    args = parser.parse_args()
    credential = args.credential_file.expanduser().read_text().strip()
    if not credential:
        raise SystemExit("Credential file is empty")
    args.output.mkdir(parents=True, exist_ok=True)
    sectors = [args.pack] if args.pack else ["finance", "manufacturing", "pharma", "power"]
    reports = []
    with tempfile.TemporaryDirectory(prefix="helios-builder-live-state-") as state:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(run_pack, sector, credential, args.output, Path(state), args.model, args.attach_sample) for sector in sectors]
            for completed in as_completed(pending):
                report = completed.result()
                reports.append(report)
                print(json.dumps({k: report[k] for k in ("pack", "status", "llm_calls", "elapsed_seconds")}), flush=True)
    (args.output / "results.json").write_text(json.dumps(reports, indent=2, default=str))
    return 0 if all(r["status"] == "generated_and_executable" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
