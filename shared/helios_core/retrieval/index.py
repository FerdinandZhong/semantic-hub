"""Immutable release retrieval with permission filtering before lexical ranking."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
import threading
from collections import defaultdict, deque

import sqlglot
from sqlglot import exp


class Clarification(ValueError):
    """The request cannot produce an unambiguous, permitted, bounded bundle."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _rule_key(key):
    normalized = str(key).lower()
    return ("mandatory" in normalized or "row_filter" in normalized
            or normalized.endswith(("_filter", "_filters", "_policy", "_policies", "_rule", "_rules"))
            or normalized in {
        "filters", "filter", "predicate", "predicates", "policy", "policies", "executable", "rules", "rule", "security_filter"})


def _has_rule(value):
    if isinstance(value, dict):
        return any(_rule_key(key) or _has_rule(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_has_rule(child) for child in value)
    return False


_BUSINESS_TEXT = {"unit", "grain", "time_rule", "owner", "rationale"}
_BUSINESS_LISTS = {"synonyms", "example_questions", "inclusion_rules", "exclusion_rules",
                   "ontology_concepts", "evidence_refs", "assumptions"}


def _business_context(value):
    """Reviewed descriptive metadata never inserts executable query rules."""
    if not isinstance(value, dict) or set(value) - (_BUSINESS_TEXT | _BUSINESS_LISTS):
        raise Clarification("Unsupported business context attribute.")
    for key, item in value.items():
        if key in _BUSINESS_TEXT:
            if not isinstance(item, str) or len(item) > 2000:
                raise Clarification("Invalid business context text.")
        elif (not isinstance(item, list) or len(item) > 50
              or not all(isinstance(text, str) and len(text) <= 2000 for text in item)):
            raise Clarification("Invalid business context terms.")
    return copy.deepcopy(value)


def _extension(item):
    result = {}
    if any(_rule_key(k) for k in item):
        raise Clarification("Unsupported mandatory semantic rule.")
    for entry in item.get("custom_extensions", []):
        if entry.get("vendor_name") != "HELIOS":
            try:
                opaque = json.loads(entry.get("data", "{}"))
            except (ValueError, TypeError):
                opaque = {}
            if isinstance(opaque, dict) and _has_rule(opaque):
                raise Clarification("Unsupported mandatory semantic rule.")
        if entry.get("vendor_name") == "HELIOS":
            try:
                data = json.loads(entry.get("data", "{}"))
            except (ValueError, TypeError) as error:
                raise Clarification("Invalid HELIOS extension.") from error
            if not isinstance(data, dict):
                raise Clarification("Invalid HELIOS extension.")
            rule_attributes = dict(data)
            if "business_context" in rule_attributes:
                _business_context(rule_attributes.pop("business_context"))
            if _has_rule(rule_attributes):
                raise Clarification("Unsupported mandatory semantic rule.")
            result.update(data)
    return result


_SERVING_KEYS = {
    "model": {"name", "version", "description"},
    "dataset": {"name", "source", "description", "primary_key"},
    "field": {"name", "description", "expression", "datatype", "label", "dimension"},
    "metric": {"name", "description", "expression", "datatype"},
    "relationship": {"name", "description", "from", "to", "from_columns", "to_columns"},
}
_EXTENSION_KEYS = {"model": set(), "dataset": {"kind"}, "field": {"role"},
                   "metric": {"dataset", "business_context"}, "relationship": {"is_default", "source", "confidence"}}


def _project(item, kind):
    """Only reviewed executable attributes and descriptive text enter serving context."""
    result = {key: copy.deepcopy(item[key]) for key in _SERVING_KEYS[kind] if key in item}
    for key in {"name", "version", "description", "source", "datatype", "label", "from", "to"} & result.keys():
        if not isinstance(result[key], str):
            raise Clarification("Invalid semantic text attribute.")
    if "expression" in result:
        result["expression"] = {"dialects": [{key: entry[key] for key in ("dialect", "expression") if key in entry}
                                            for entry in result["expression"].get("dialects", [])]}
    if "expression" in result:
        if not all(isinstance(value, str) for entry in result["expression"]["dialects"] for value in entry.values()):
            raise Clarification("Invalid semantic expression attribute.")
    if "dimension" in result:
        result["dimension"] = {key: value for key, value in result["dimension"].items() if key == "is_time"}
        if any(not isinstance(value, bool) for value in result["dimension"].values()):
            raise Clarification("Invalid semantic dimension attribute.")
    context = item.get("ai_context")
    if isinstance(context, dict) and "synonyms" in context:
        synonyms = context["synonyms"]
        if not isinstance(synonyms, list) or not all(isinstance(value, str) for value in synonyms):
            raise Clarification("Invalid semantic synonyms.")
        result["ai_context"] = {"synonyms": copy.deepcopy(synonyms)}
    extension = _extension(item)
    reviewed = {key: extension[key] for key in _EXTENSION_KEYS[kind] if key in extension}
    if reviewed:
        for key, value in reviewed.items():
            if key == "business_context":
                reviewed[key] = _business_context(value)
                continue
            expected = bool if key == "is_default" else (int, float) if key == "confidence" else str
            if not isinstance(value, expected):
                raise Clarification("Invalid semantic extension attribute.")
        result["custom_extensions"] = [{"vendor_name": "HELIOS", "data": _json(reviewed)}]
    return result


class SemanticIndex:
    def __init__(self, document):
        self._document = copy.deepcopy(document)
        _extension(self._document)
        self._document_sha256 = hashlib.sha256(_json(self._document).encode()).hexdigest()
        self._datasets = {d["name"]: d for d in self._document.get("datasets", [])}
        self._fields = {f'{d["name"]}.{f["name"]}': f for d in self._datasets.values() for f in d.get("fields", [])}
        self._metrics = {m["name"]: m for m in self._document.get("metrics", [])}
        if len(self._datasets) != len(self._document.get("datasets", [])) or len(self._metrics) != len(self._document.get("metrics", [])):
            raise Clarification("Duplicate semantic names.")
        if len(self._fields) != sum(len(d.get("fields", [])) for d in self._datasets.values()):
            raise Clarification("Duplicate field names.")
        self._aliases = defaultdict(set)
        for name, d in self._datasets.items():
            self._aliases[name].add(name)
            self._aliases[d["source"]].add(name)
        self._unqualified = defaultdict(set)
        for key, field in self._fields.items():
            self._unqualified[field["name"]].add(key)
            if field.get("label"):
                self._unqualified[field["label"]].add(key)
        self._deps = {key: self._dependencies(f, key.rsplit(".", 1)[0]) for key, f in self._fields.items()}
        complete, visiting = set(), set()
        def validate_cycle(key):
            if key in visiting:
                raise Clarification("Computed field dependency cycle.")
            if key in complete:
                return
            visiting.add(key)
            for dependency in self._deps[key] - {key}:
                validate_cycle(dependency)
            visiting.remove(key)
            complete.add(key)
        for key in self._fields:
            validate_cycle(key)
        self._closures = {key: self._expand({key}) for key in self._fields}
        self._mandatory = {}
        for name, dataset in self._datasets.items():
            extension = _extension(dataset)
            if any("mandatory" in str(k).lower() or "row_filter" in str(k).lower() for k in extension):
                raise Clarification("Unsupported mandatory semantic rule.")
            self._mandatory[name] = self._expand({self._resolve(f, name) for f in dataset.get("primary_key", [])})
        self._metric_closures = {}
        for name, metric in self._metrics.items():
            dataset = _extension(metric).get("dataset")
            if dataset:
                aliases = self._aliases.get(dataset, set())
                if len(aliases) != 1:
                    raise Clarification("Metric dataset is missing or ambiguous.")
                dataset = next(iter(aliases))
            keys = self._dependencies(metric, dataset)
            if not keys:
                if dataset is None and len(self._datasets) == 1:
                    dataset = next(iter(self._datasets))
                if dataset not in self._datasets:
                    raise Clarification("Metric source is ambiguous.")
                # COUNT(*) requires a source but must not widen the entire dataset.
                available = sorted(k for k in self._fields if k.rsplit(".", 1)[0] == dataset)
                if not available:
                    raise Clarification("Metric source has no fields.")
                keys.add(available[0])
            self._metric_closures[name] = self._expand(keys)
        self._relations = {}
        self._adjacency = defaultdict(list)
        for rel in self._document.get("relationships", []):
            _extension(rel)
            name = rel["name"]
            if name in self._relations:
                raise Clarification("Duplicate relationship name.")
            keys = {self._resolve(f, rel["from"]) for f in rel["from_columns"]} | {self._resolve(f, rel["to"]) for f in rel["to_columns"]}
            self._relations[name] = (rel, self._expand(keys))
            self._adjacency[rel["from"]].append(name)
            self._adjacency[rel["to"]].append(name)
        self._components = {}
        for start in self._datasets:
            if start in self._components:
                continue
            component, pending = set(), [start]
            while pending:
                current = pending.pop()
                if current in component:
                    continue
                component.add(current)
                for relname in self._adjacency[current]:
                    rel = self._relations[relname][0]
                    pending.extend([rel["from"], rel["to"]])
            for name in component:
                self._components[name] = frozenset(component)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute("CREATE VIRTUAL TABLE definitions USING fts5(kind UNINDEXED, name UNINDEXED, terms, description)")
        self._requirements = {}
        for kind, objects, closures in (("field", self._fields, self._closures), ("metric", self._metrics, self._metric_closures)):
            for name, item in objects.items():
                required = set(closures[name])
                required = self._with_mandatory(required)
                terms = " ".join([name, item.get("label", ""), *item.get("ai_context", {}).get("synonyms", [])])
                business = _extension(item).get("business_context", {}) if kind == "metric" else {}
                terms += " " + " ".join(business.get("synonyms", []))
                descriptors = [item.get("description", "")]
                descriptors.extend(business.get(key, "") for key in ("unit", "grain", "time_rule"))
                for key in ("example_questions", "ontology_concepts", "inclusion_rules", "exclusion_rules"):
                    descriptors.extend(business.get(key, []))
                cursor = self._db.execute("INSERT INTO definitions(kind,name,terms,description) VALUES(?,?,?,?)", (kind, name, terms, " ".join(descriptors)))
                self._requirements[cursor.lastrowid] = frozenset(required)
        self._db.commit()
        self._db.execute("PRAGMA query_only=ON")

    @property
    def document_sha256(self):
        return self._document_sha256

    @property
    def document(self):
        return copy.deepcopy(self._document)

    def _resolve(self, reference, default=None):
        if "." in reference:
            dataset, field = reference.rsplit(".", 1)
            aliases = self._aliases.get(dataset, set())
            if len(aliases) != 1:
                raise Clarification("Field dataset is missing or ambiguous.")
            key = f"{next(iter(aliases))}.{field}"
        elif default:
            key = f"{default}.{reference}"
        else:
            matches = self._unqualified.get(reference, set())
            if len(matches) != 1:
                raise Clarification("Field reference is missing or ambiguous.")
            key = next(iter(matches))
        if key not in self._fields:
            raise Clarification("Unknown semantic field dependency.")
        return key

    def _dependencies(self, item, default=None):
        extension = _extension(item)
        if any("mandatory" in str(k).lower() or "row_filter" in str(k).lower() for k in extension):
            raise Clarification("Unsupported mandatory semantic rule.")
        keys = set()
        for entry in item.get("expression", {}).get("dialects", []):
            try:
                ast = sqlglot.parse_one(entry["expression"])
            except (sqlglot.errors.ParseError, TypeError) as error:
                raise Clarification("Cannot parse semantic expression.") from error
            if ast is None:
                raise Clarification("Empty semantic expression.")
            for column in ast.find_all(exp.Column):
                reference = ".".join(part.name for part in column.parts)
                keys.add(self._resolve(reference, default))
        return keys

    def _expand(self, keys):
        result, pending = set(), list(keys)
        while pending:
            key = pending.pop()
            if key not in result:
                result.add(key)
                pending.extend(self._deps.get(key, set()) - result)
        return frozenset(result)

    def _with_mandatory(self, keys):
        result = set(keys)
        pending = {k.rsplit(".", 1)[0] for k in result}
        seen = set()
        while pending:
            dataset = pending.pop()
            if dataset in seen:
                continue
            seen.add(dataset)
            result.update(self._mandatory[dataset])
            pending.update(k.rsplit(".", 1)[0] for k in result if k.rsplit(".", 1)[0] not in seen)
        return result

    def search(self, question, allowed_fields=None, limit=10):
        return self._search(question, allowed_fields, limit)

    def _search(self, question, allowed_fields=None, limit=10, kind=None):
        words = [word for word in dict.fromkeys(re.findall(r"[^\W_]+", question.lower()))
                 if word not in {"show", "what", "the", "is", "of", "and", "by", "for", "in", "a", "me", "grouped"}]
        if not words or limit <= 0:
            return []
        match = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
        permitted = lambda row: allowed_fields is None or self._requirements[row] <= allowed_fields
        with self._lock:
            # Ranking uses only row-local terms. Forbidden corpus statistics cannot affect it.
            def rank(terms, description):
                term_words = set(re.findall(r"[^\W_]+", terms.lower()))
                description_words = set(re.findall(r"[^\W_]+", description.lower()))
                return 4 * len(set(words) & term_words) + len(set(words) & description_words)
            self._db.create_function("permitted", 1, permitted)
            self._db.create_function("lexical_rank", 2, rank)
            rows = self._db.execute("SELECT kind,name,lexical_rank(terms,description) AS score FROM definitions WHERE definitions MATCH ? AND permitted(rowid) AND (? IS NULL OR kind=?) ORDER BY score DESC,kind,name LIMIT ?", (match, kind, kind, limit)).fetchall()
        return [{"kind": kind, "name": name, "score": score} for kind, name, score in rows]

    def bundle(self, question, allowed_fields=None, max_datasets=5, max_fields=100, max_chars=24000, max_tokens=6000, token_counter=None, metric=None, required_fields=None):
        for value in (max_datasets, max_fields, max_chars, max_tokens):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise Clarification("Context limits must be positive integers.")
        matches = self.search(question, allowed_fields)
        if metric is not None:
            if metric not in self._metrics:
                raise Clarification("Unknown requested metric.")
            required = self._metric_closures[metric]
            if allowed_fields is not None and not required <= allowed_fields:
                raise Clarification("Requested metric has forbidden dependencies.")
            matches = [{"kind": "metric", "name": metric, "score": 1.0}]
        if not matches:
            raise Clarification("No permitted semantic definition matched.")
        metric_hits = ([m for m in matches if m["kind"] == "metric"] if metric is not None
                       else self._search(question, allowed_fields, 10, kind="metric"))
        if metric is None and len(metric_hits) > 1 and metric_hits[0]["score"] == metric_hits[1]["score"]:
            raise Clarification("Choose an unambiguous metric.")
        if metric_hits:
            anchor = metric_hits[0]
            roots = {k.rsplit(".", 1)[0] for k in self._metric_closures[anchor["name"]]}
            component = set().union(*(self._components[root] for root in roots))
            question_words = set(re.findall(r"[^\W_]+", question.lower())) - {"show", "what", "the", "is", "of", "and", "by", "for", "in", "a", "me", "grouped"}
            with self._lock:
                def relevant(rowid, name, terms):
                    if allowed_fields is not None and not self._requirements[rowid] <= allowed_fields:
                        return False
                    if name.rsplit(".", 1)[0] not in component:
                        return False
                    field = self._fields[name]
                    explicit = " ".join([field["name"], field.get("label", ""), *field.get("ai_context", {}).get("synonyms", [])])
                    return bool(question_words & set(re.findall(r"[^\W_]+", explicit.lower())))
                self._db.create_function("relevant_field", 3, relevant)
                words = list(dict.fromkeys(re.findall(r"[^\W_]+", question.lower())))
                match_query = " OR ".join('"' + word + '"' for word in words)
                rows = self._db.execute("SELECT kind,name,lexical_rank(terms,description) AS score FROM definitions WHERE definitions MATCH ? AND kind='field' AND relevant_field(rowid,name,terms) ORDER BY score DESC,name LIMIT 9", (match_query,)).fetchall()
            matches = [anchor] + [{"kind": k, "name": n, "score": v} for k, n, v in rows]
        if required_fields is not None:
            if metric is None or not isinstance(required_fields, (list, tuple)) or len(required_fields) > max_fields:
                raise Clarification("Explicit fields require a selected metric and bounded field list.")
            matches = [{"kind": "metric", "name": metric, "score": 1.0}]
            for name in required_fields:
                if not isinstance(name, str) or name not in self._fields:
                    raise Clarification("Unknown explicitly requested field.")
                if allowed_fields is not None and not self._closures[name] <= allowed_fields:
                    raise Clarification("Explicitly requested field has forbidden dependencies.")
                matches.append({"kind": "field", "name": name, "score": 1.0})
        keys, names = set(), set()
        for match in matches:
            if match["kind"] == "metric":
                names.add(match["name"])
                keys.update(self._metric_closures[match["name"]])
            else:
                keys.update(self._closures[match["name"]])
        selected_relations = set()
        datasets = {k.rsplit(".", 1)[0] for k in keys}
        if datasets:
            root = sorted(datasets)[0]
            for target in sorted(datasets - {root}):
                queue, paths = deque([(root, [], frozenset({root}))]), []
                expansions = 0
                while queue:
                    expansions += 1
                    if expansions > 10000:
                        raise Clarification("Join dependency search exceeds the bounded graph budget.")
                    current, path, visited = queue.popleft()
                    if current == target:
                        paths.append(path)
                        if len(paths) > 1:
                            raise Clarification("Multiple permitted join paths require clarification.")
                        continue
                    if len(path) >= max_datasets - 1:
                        continue
                    grouped = defaultdict(list)
                    for name in self._adjacency[current]:
                        rel, dependencies = self._relations[name]
                        if allowed_fields is not None and not dependencies <= allowed_fields:
                            continue
                        other = rel["to"] if rel["from"] == current else rel["from"]
                        grouped[other].append(name)
                    for other, alternatives in sorted(grouped.items()):
                        if other in visited:
                            continue
                        if len(alternatives) > 1:
                            defaults = [n for n in alternatives if _extension(self._relations[n][0]).get("is_default")]
                            if len(defaults) != 1:
                                raise Clarification("Multiple permitted relationships require clarification.")
                            alternatives = defaults
                        queue.append((other, path + alternatives, visited | {other}))
                if not paths:
                    raise Clarification("Selected definitions have no permitted join path.")
                selected_relations.update(paths[0])
        for name in selected_relations:
            keys.update(self._relations[name][1])
        keys = self._with_mandatory(keys)
        if allowed_fields is not None and not keys <= allowed_fields:
            raise Clarification("Required semantic dependencies are forbidden.")
        datasets = {k.rsplit(".", 1)[0] for k in keys}
        doc = _project(self._document, "model")
        doc.update(datasets=[], metrics=[_project(self._metrics[n], "metric") for n in sorted(names)], relationships=[_project(self._relations[n][0], "relationship") for n in sorted(selected_relations)])
        for name in sorted(datasets):
            original = self._datasets[name]
            dataset = _project(original, "dataset")
            dataset["fields"] = [_project(f, "field") for f in original.get("fields", []) if f'{name}.{f["name"]}' in keys]
            doc["datasets"].append(dataset)
        serialized = _json(doc)
        token_count = token_counter(serialized) if token_counter else len(serialized.encode("utf-8"))
        if not isinstance(token_count, int) or isinstance(token_count, bool) or token_count < 0:
            raise Clarification("Invalid tokenizer result.")
        if len(datasets) > max_datasets or len(keys) > max_fields or len(serialized) > max_chars or token_count > max_tokens:
            raise Clarification("Required semantic dependencies exceed the context budget.")
        return {"document": doc, "evidence": {"release_sha256": self.document_sha256, "method": "permission-filtered SQLite FTS5", "matches": matches, "dataset_count": len(datasets), "field_count": len(keys), "context_chars": len(serialized), "context_tokens": token_count, "token_count_method": "configured tokenizer" if token_counter else "conservative UTF-8 byte upper bound", "limits": {"datasets": max_datasets, "fields": max_fields, "context_chars": max_chars, "context_tokens": max_tokens}}}
