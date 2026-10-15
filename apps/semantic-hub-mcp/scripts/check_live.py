"""Read published pharma semantics through actual MCP stdio and the HTTP API.

This check makes no LLM calls and performs no draft, publication, or model writes.
"""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def check(url: str, token_file: Path | None, embedding: bool = False, package_source: str | None = None) -> dict:
    token = token_file.read_text().strip() if token_file else ""
    if token_file and not token:
        raise ValueError("The token file is empty.")
    source = str(Path(__file__).resolve().parents[1] / "src")
    env = {**os.environ, "SEMANTIC_HUB_URL": url, "SEMANTIC_HUB_API_TOKEN": token}
    if package_source:
        env.pop("PYTHONPATH", None)
        params = StdioServerParameters(command="uvx", args=["--from", package_source, "semantic-hub-mcp"], env=env)
    else:
        params = StdioServerParameters(command=sys.executable, args=["-m", "semantic_hub_mcp.server"],
                                      env={**env, "PYTHONPATH": source})
    calls = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            discovered = await session.list_tools()
            assert len(discovered.tools) == 12, "Expected twelve read-only MCP tools."

            async def call(name: str, **arguments):
                result = await session.call_tool(name, arguments)
                assert not result.is_error, f"MCP tool failed: {name}"
                data = result.structured_content
                if data is None:
                    data = json.loads(next(c.text for c in result.content if c.type == "text"))
                assert data.get("ok") is not False, f"Hub request failed: {name}: {data.get('error')}"
                calls.append(name)
                return data

            capabilities = await call("hub_status")
            models = await call("list_semantic_models", q="pharma", limit=20)
            model = next(m for m in models["items"] if m["model_id"] == "pharma_intelligence")
            model_id = model["model_id"]
            await call("get_semantic_model", model_id=model_id)
            versions = await call("list_model_versions", model_id=model_id)
            version = next(v for v in versions["versions"] if v["version"] == "v1.0")
            binding = {"model_id": model_id, "version": version["version"], "context_sha256": version["context_sha256"]}
            await call("get_model_version", **binding)
            await call("get_model_lineage", **binding)
            await call("get_published_documents", **binding)
            search = await call("search_semantics", **binding, query="new medicine sales share", mode="keyword", limit=10)
            assert search["method"] == "keyword" and search["items"], "Keyword search returned no candidates."
            embedding_result = None
            if embedding:
                found = await call("search_semantics", **binding, query="US new medicine sales share", mode="embedding", limit=3)
                assert found["method"] == "embedding" and found["items"], "Embedding search returned no candidates."
                embedding_result = {"method": found["method"], "embedding_model": found.get("embedding_model"),
                                    "storage": found.get("storage"), "result_count": len(found["items"]),
                                    "top_names": [item["name"] for item in found["items"]]}
            metric = "us_new_medicine_sales_share_percent"
            missing_question = "What is the US share of sales for new medicines launched during 1999–2020?"
            question = "What is the US share of sales for new medicines launched during 2020–2024?"
            resolved = await call("resolve_semantic_context", **binding, query=question, metric=metric,
                                  required_fields=["industry_observations.period_start", "industry_observations.period_end"])
            assert resolved["status"] == "ready", "Semantic resolution did not return a ready bundle."
            coverage = await call("inspect_metric_coverage", **binding, metric=metric, question=missing_question)
            assert coverage["status"] == "no_data", "Unavailable 1999–2020 cohort must report no_data."
            query = {**binding, "bundle_id": resolved["bundle_id"], "question": question,
                     "metrics": [metric], "dimensions": [], "filters": [], "limit": 10}
            compiled = await call("compile_semantic_query", **query)
            assert compiled["status"] == "ready" and compiled["sql"], "Compilation did not return SQL."
            answer = await call("query_sample_data", **query)
            assert answer["status"] == "answered", "Sample execution did not return an answer."
            assert len(answer["rows"]) == 1 and len(answer["rows"][0]) == 1, "Expected one scalar result."
            assert math.isclose(float(answer["rows"][0][0]), 74.1, abs_tol=1e-8), "Expected sample value 74.1."
            return {"ok": True, "transport": "stdio -> HTTP", "package_source": package_source or "local source", **binding, "tools_discovered": len(discovered.tools),
                    "calls": calls, "missing_cohort_status": coverage["status"], "sample_value": answer["rows"][0][0],
                    "generation_llm_calls": 0, "model_writes": 0, "capabilities": capabilities,
                    "embedding_check": embedding_result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Dedicated consumer API server origin")
    parser.add_argument("--token-file", type=Path, help="Omit for the local no-auth API")
    parser.add_argument("--package-source", help="Git package URL to install through uvx instead of the local source")
    parser.add_argument("--embedding", action="store_true", help="Also run one pinned embedding search; may call the configured embedding provider")
    parser.add_argument("--output", type=Path, help="Write the redacted JSON report to this path")
    args = parser.parse_args()
    report = json.dumps(asyncio.run(check(args.url, args.token_file, args.embedding, args.package_source)), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
