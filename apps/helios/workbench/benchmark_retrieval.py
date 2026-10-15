"""Reproducible offline retrieval benchmark; labels never enter the index.

Run: PYTHONPATH=shared python apps/helios/workbench/benchmark_retrieval.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path


DOMAINS = "aviation bakery ceramics dentistry electronics forestry gardening hospitality insurance jewelry logistics mining nutrition optics pharmacy quilting robotics shipping textiles utilities".split()


def expression(sql):
    return {"dialects": [{"dialect": "ANSI_SQL", "expression": sql}]}


def fixture():
    datasets, metrics, relationships, labels = [], [], [], []
    for i in range(2000):
        domain = DOMAINS[(i // 2) % len(DOMAINS)]
        target = i < 40
        dimension = target and i % 2 == 1
        name = f"{domain}_{'customers' if dimension else 'orders'}" if target else f"archive_{i:04d}"
        fields = []
        for j in range(40):
            field_name = ["customer_id", "region", "revenue", "cost"][j] if target and j < 4 else f"attribute_{j:02d}"
            fields.append({"name": field_name, "label": field_name.replace('_', ' '),
                           "description": f"{domain} {'current' if target else 'historical forecast estimate'} {field_name.replace('_', ' ')}",
                           "datatype": "String" if j < 2 else "Decimal",
                           "expression": expression(field_name), **({"dimension": {}} if j < 2 else {"measure": {}})})
        datasets.append({"name": name, "source": f"warehouse.{name}", "description": f"{domain} {'current booked business' if target else 'historical forecasts, revenue projections and cost estimates; not current bookings'}",
                         "primary_key": ["customer_id"] if dimension else [], "fields": fields})
    for domain in DOMAINS:
        fact, dim = f"{domain}_orders", f"{domain}_customers"
        metric = f"{domain}_margin"
        metrics.append({"name": metric, "description": f"{domain} booked profit after costs", "ai_context": {"synonyms": [f"{domain} booked profit"]},
                        "expression": expression(f"SUM({fact}.revenue) - SUM({fact}.cost)")})
        relationships.append({"name": f"{domain}_customer_join", "from": fact, "to": dim, "from_columns": ["customer_id"], "to_columns": ["customer_id"]})
        required = {f"{fact}.revenue", f"{fact}.cost", f"{fact}.customer_id", f"{dim}.customer_id", f"{dim}.region"}
        for query in [f"Show {domain} booked profit by region", f"{domain} margin grouped by customer region"]:
            labels.append({"question": query, "metric": metric, "candidate": metric, "required_fields": required})
    return {"name": "synthetic_retrieval_benchmark", "version": "1", "datasets": datasets, "metrics": metrics, "relationships": relationships}, labels


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def timing(values):
    return {"samples": len(values), "p50_ms": round(statistics.median(values), 3), "p95_ms": round(percentile(values, .95), 3)}


def identifiers(value):
    """Accept hit representations without assuming an implementation-specific key."""
    if isinstance(value, dict):
        found = {str(v) for k, v in value.items() if k in {"id", "name", "ref", "qualified_name", "qualified", "metric", "metric_name"} and isinstance(v, str)}
        for child in value.values():
            found |= identifiers(child)
        return found
    if isinstance(value, (list, tuple)):
        return set().union(*(identifiers(item) for item in value)) if value else set()
    return set()


def bundle_fields(bundle):
    document = bundle.get("document", {})
    return {f"{d['name']}.{f['name']}" for d in document.get("datasets", []) for f in d.get("fields", [])}


def safe_bundle(index, question, **kwargs):
    try:
        return index.bundle(question, **kwargs)
    except Exception as error:
        return {"document": {}, "evidence": {"error_type": type(error).__name__, "clarification": str(error)}}


def run():
    from helios_core.retrieval.index import SemanticIndex
    from helios_core.retrieval.service import RetrievalService, Scope
    document, labels = fixture()
    started = time.perf_counter()
    index = SemanticIndex(document)
    build_ms = (time.perf_counter() - started) * 1000
    for label in labels[:3]:
        index.search(label["question"], limit=10)
        safe_bundle(index, label["question"])
    searches, bundles, rows = [], [], []
    for label in labels:
        started = time.perf_counter()
        hits = index.search(label["question"], limit=10)
        searches.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        bundle = safe_bundle(index, label["question"])
        bundles.append((time.perf_counter() - started) * 1000)
        refs = identifiers(hits)
        selected = bundle_fields(bundle)
        payload = json.dumps(bundle.get("document", {}), ensure_ascii=False, separators=(",", ":"))
        rows.append({"question": label["question"], "expected_metric": label["metric"],
                     "candidate_recall_at_1": int(label["candidate"] in identifiers(hits[:1])),
                     "candidate_recall_at_5": int(label["candidate"] in identifiers(hits[:5])),
                     "candidate_recall_at_10": int(label["candidate"] in refs),
                     "bundle_succeeded": "error_type" not in bundle.get("evidence", {}),
                     "dependency_recall": len(label["required_fields"] & selected) / len(label["required_fields"]),
                     "missing_fields": sorted(label["required_fields"] - selected), "document_chars": len(payload),
                     "evidence": bundle.get("evidence", {})})
    probe = labels[0]
    allowed = {f"{DOMAINS[0]}_customers.region"}
    restricted = safe_bundle(index, probe["question"], allowed_fields=allowed)
    restricted_hits = index.search(probe["question"], allowed_fields=allowed, limit=10)
    ambiguity = safe_bundle(index, "Show revenue by region")
    budget = safe_bundle(index, probe["question"], max_chars=700, max_tokens=175, metric=probe["metric"])
    service = RetrievalService()
    started = time.perf_counter()
    manifest = service.register("benchmark", "v1", document, publication={"status": "published", "source": "offline-synthetic-fixture", "reference": "deterministic-v1"})
    service_register_ms = (time.perf_counter() - started) * 1000
    scope = Scope("benchmark-reader", "benchmark-policy-v1", {"benchmark": manifest.get("release_id", manifest["document_sha256"])}, {"benchmark": None})
    uncached_times, cached_times, service_checks = [], [], []
    ready_uncached, actual_cached = [], []
    for label in labels:
        started = time.perf_counter()
        first = service.resolve_context(label["question"], scope)
        uncached_times.append((time.perf_counter() - started) * 1000)
        if first["status"] == "ready":
            ready_uncached.append(uncached_times[-1])
        started = time.perf_counter()
        second = service.resolve_context(label["question"], scope)
        cached_times.append((time.perf_counter() - started) * 1000)
        if second.get("evidence", {}).get("cache_hit"):
            actual_cached.append(cached_times[-1])
        service_checks.append({"question": label["question"], "first_status": first["status"], "second_status": second["status"],
                               "second_cache_hit": second.get("evidence", {}).get("cache_hit", False),
                               "same_bundle_id": first.get("bundle_id") is not None and first.get("bundle_id") == second.get("bundle_id")})
    dependency = statistics.mean(row["dependency_recall"] for row in rows)
    recall = statistics.mean(row["candidate_recall_at_10"] for row in rows)
    successful = [r for r in rows if r["bundle_succeeded"]]
    failures = {}
    for row in rows:
        if not row["bundle_succeeded"]:
            reason = row["evidence"].get("clarification", "unknown")
            failures[reason] = failures.get(reason, 0) + 1
    return {"fixture": {"tables": 2000, "fields_per_table": 40, "fields": 80000, "metrics": 20,
                        "queries": len(labels), "warmup_queries": 3, "seed": "deterministic-v1", "python": platform.python_version(),
                        "platform": platform.system(), "architecture": platform.machine(), "cpu_count": os.cpu_count()},
            "index_build_ms": round(build_ms, 3),
            "service_register_ms": round(service_register_ms, 3),
            "service_uncached_resolve": timing(uncached_times), "service_repeated_resolve": timing(cached_times),
            "service_ready_uncached_resolve": timing(ready_uncached) if ready_uncached else None,
            "service_actual_cached_resolve": timing(actual_cached) if actual_cached else None,
            "successful_full_bundle": timing([elapsed for elapsed, row in zip(bundles, rows) if row["bundle_succeeded"]]) if successful else None,
            "service_cache_hits": sum(row["second_cache_hit"] for row in service_checks), "service_checks": service_checks, "warm_search": timing(searches), "warm_full_bundle": timing(bundles),
            "candidate_recall_at_1": statistics.mean(r["candidate_recall_at_1"] for r in rows),
            "candidate_recall_at_5": statistics.mean(r["candidate_recall_at_5"] for r in rows),
            "candidate_recall_at_10": recall, "dependency_recall": dependency,
            "successful_bundles": len(successful), "bundle_failures": failures,
            "document_chars": {"p50": statistics.median(r["document_chars"] for r in successful) if successful else None, "max": max((r["document_chars"] for r in successful), default=None)},
            "budget_token_count": {"method": "conservative UTF-8 byte upper bound",
                                   "p50": statistics.median(r["evidence"]["context_tokens"] for r in successful) if successful else None,
                                   "max": max((r["evidence"]["context_tokens"] for r in successful), default=None)},
            "permission_negative": {"allowed_fields": sorted(allowed), "unauthorized_fields": sorted(bundle_fields(restricted) - allowed),
                                    "returned_metric_names": sorted(identifiers(restricted_hits) & {m['name'] for m in document['metrics']}), "evidence": restricted.get("evidence", {})},
            "clarification_probe": {"question": "Show revenue by region", "evidence": ambiguity.get("evidence", {})},
            "budget_probe": {"max_chars": 700, "max_tokens": 175, "evidence": budget.get("evidence", {})},
            "scope_limits": "Offline, in-process core benchmark on synthetic data. Index build and service registration are separate startup measurements. Service resolve includes trusted scope validation, retrieval, bundle construction, evidence and caching. Excludes HTTP transport, authentication middleware, network, real tokenizer, model inference and SQL execution.",
            "analysis": f"Candidate recall {recall:.3f}; dependency recall {dependency:.3f}. Successful bundles {len(successful)}/{len(rows)}. Failed bundles count as zero dependency recall. Payload sizes cover successful bundles only. Inspect missing fields and clarification evidence; no success threshold is assumed.",
            "queries": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/retrieval-benchmark.json")
    args = parser.parse_args()
    result = run()
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"queries", "service_checks"}}, indent=2))
