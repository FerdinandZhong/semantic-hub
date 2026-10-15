"""Source-only proposal staging. Applying a candidate never approves a draft."""
from __future__ import annotations

import copy
import csv
import io
import json
import re
import uuid

import sqlglot
from sqlglot import exp

from helios_core.propose.propose import Proposer
from .context import ContextBinding, ContextDefinition, ContextWorkspace, ProposalProvenance, now
from .registry import DemoError, canonical
from pydantic import Field, AliasChoices
from typing import Literal


class GenerateProposal(ContextBinding):
    revision: int = Field(ge=0)
    mode: Literal["evidence", "llm"] = "evidence"


class ApplyProposal(ContextBinding):
    revision: int = Field(ge=0)
    proposal_id: str = Field(min_length=1, max_length=80, validation_alias=AliasChoices("proposal_id", "candidate_id"))


class ProposalWorkspace:
    def __init__(self, workspace: ContextWorkspace):
        self.workspace = workspace

    def evidence(self):
        tables, profiles = [], {}
        for table in self.workspace.pack.tables:
            key = 'source.' + table.name
            rows = list(csv.DictReader(io.StringIO(table.csv_bytes.decode())))
            stats = {}
            for name, dtype in table.columns:
                values = [r[name] for r in rows if r.get(name) not in ('', None)]
                stats[name] = {'type': dtype, 'ndv': len(set(values)), 'null_rate': 1 - len(values) / max(len(rows), 1)}
            source_ds = next((d for d in self.workspace._source['datasets'] if d['name'] == table.name), {})
            tables.append({'database': 'source', 'table': table.name, 'description': source_ds.get('description', ''),
                           'columns': [{'name': n, 'type': t} for n, t in table.columns]})
            profiles[key] = {'primary_keys': [{'column': c} for c in source_ds.get('primary_key', [])], 'stats': {'row_count': table.row_count, 'columns': stats}}
        relationships = []
        for rel in self.workspace._source.get('relationships', []):
            relationships.append({'from': 'source.' + rel['from'], 'to': 'source.' + rel['to'],
                                  'from_column': rel['from_columns'][0], 'to_column': rel['to_columns'][0]})
        return ({'tables': tables, 'glossary_terms': [], 'queries': {'statements': []}},
                {'tables': profiles, 'relationships': relationships, 'suggested_relationships': []})

    def view(self):
        with self.workspace.connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, content TEXT NOT NULL)')
            return {'items': [json.loads(r[0]) for r in conn.execute('SELECT content FROM proposals ORDER BY rowid DESC LIMIT 20')]}

    def generate(self, revision: int, mode='evidence', llm=None):
        with self.workspace.connection() as conn:
            draft = self.workspace._draft(conn, revision)
        if mode not in ('evidence', 'llm'):
            raise DemoError('Unknown proposal mode')
        if mode == 'llm' and llm is None:
            raise DemoError('Configure an LLM provider before requesting an LLM proposal')
        harvest, profile = self.evidence()
        source_documents = [
            {'citation': 'document:' + document.document_id,
             'text': document.content_bytes.decode('utf-8', errors='replace')[:1500]}
            for document in getattr(self.workspace.pack, 'documents', ())
        ]
        attachments = []
        if draft['definition'].get('document_attachments'):
            from .builder_artifacts import BuilderArtifacts
            attachments = [
                {'citation': document['citation'], 'text': document['content'][:1500]}
                for document in BuilderArtifacts(self.workspace).resolve(draft['definition']['document_attachments'])
            ]
        selected_attachments = list(reversed(attachments))[:2]
        documents = selected_attachments + source_documents[:5 - len(selected_attachments)]
        if len(documents) < 5:
            documents.extend(list(reversed(attachments))[2:2 + 5 - len(documents)])
        coverage = {'selected_citations': [document['citation'] for document in documents],
                    'selected_count': len(documents), 'total_count': len(source_documents) + len(attachments),
                    'source_count': len(source_documents), 'attachment_count': len(attachments),
                    'document_limit': 5, 'characters_per_document': 1500}
        for table in harvest['tables']:
            table['source_documents'] = documents
        value = copy.deepcopy(draft['definition'])
        warnings = []
        if coverage['selected_count'] < coverage['total_count']:
            warnings.append(f"Document evidence covers {coverage['selected_count']} of {coverage['total_count']} documents; selected citations are recorded in evidence.document_coverage.")
        if mode == 'llm':
            allowed_refs = {f'table:{t.name}' for t in self.workspace.pack.tables} | {f'field:{field}' for field in self.workspace._fields} | {d['citation'] for d in documents}
            allowed_concepts = (
                {t.name for t in self.workspace.pack.tables} | set(self.workspace._fields)
                | {concept for metric in draft['definition']['metrics'] for concept in metric.get('ontology_concepts', [])}
                | {term['term'] for term in draft['definition'].get('glossary_terms', []) if isinstance(term.get('term'), str)}
            )
            source_metrics = [{k: v for k, v in metric.items() if k not in {'reference_sql', 'filters'}} for metric in draft['definition']['metrics']]
            source_tables = sorted({'source.' + c.table for metric in source_metrics for c in sqlglot.parse_one(metric['expression']).find_all(exp.Column)})
            guidance = {'source_metric_tables': source_tables, 'source_metrics': source_metrics, 'evidence_refs': sorted(allowed_refs), 'ontology_concepts': sorted(allowed_concepts), 'source_documents': documents[:5]}
            proposed = Proposer(llm, max_queries=0, metric_guidance=guidance).run(harvest, profile, log=lambda _: None)
            value['metrics'] = []
            known = {m['name']: m.get('id', '') for m in draft['definition']['metrics']}
            if len(proposed['metrics']) > 20:
                raise DemoError('Proposal exceeded the 20 metric review limit; draft preserved')
            value['dataset_meanings'] = {}
            value['field_roles'] = {}
            value['glossary_terms'] = proposed['glossary_terms']
            for term in value['glossary_terms']:
                for column in term.get('columns', []):
                    if column.removeprefix('source.') not in self.workspace._fields:
                        raise DemoError('Proposal glossary invented a source field')
            for relationship in proposed['relationships']:
                for side in ('from', 'to'):
                    field = relationship[side].removeprefix('source.') + '.' + relationship[side + '_column']
                    if field not in self.workspace._fields:
                        raise DemoError('Proposal invented a relationship field')
            for m in proposed['metrics']:
                dataset = m['dataset'].removeprefix('source.')
                tree = sqlglot.parse_one(m['expression'])
                for c in tree.find_all(exp.Column):
                    if c.catalog or (c.db and c.db != 'source') or (c.table and c.table != dataset):
                        raise DemoError('Proposal invented a metric dataset')
                    c.set('db', None)
                    c.set('table', exp.to_identifier(dataset))
                    if f'{dataset}.{c.name}' not in self.workspace._fields:
                        raise DemoError('Proposal invented a metric column')
                name = re.sub(r'[^a-z0-9_]+', '_', m['name'].lower()).strip('_')[:64]
                if not name or not name[0].isalpha():
                    raise DemoError('Proposal metric name is invalid')
                metadata = {k: m[k] for k in ('unit', 'grain', 'time_rule', 'synonyms', 'example_questions', 'owner',
                    'inclusion_rules', 'exclusion_rules', 'ontology_concepts', 'evidence_refs', 'rationale', 'assumptions') if k in m}
                for key in ('synonyms', 'example_questions', 'inclusion_rules', 'exclusion_rules',
                            'ontology_concepts', 'evidence_refs', 'assumptions'):
                    if key not in metadata:
                        continue
                    if isinstance(metadata[key], str):
                        metadata[key] = [metadata[key]] if metadata[key] else []
                        warnings.append(f'{name}: normalized {key} string into a list; review the metadata.')
                    if not isinstance(metadata[key], list) or any(not isinstance(item, str) for item in metadata[key]):
                        raise DemoError(f'Proposal {key} must be a string list; draft preserved')
                if any(ref not in allowed_refs for ref in metadata.get('evidence_refs', [])):
                    raise DemoError('Proposal invented an evidence reference')
                if any(concept not in allowed_concepts for concept in metadata.get('ontology_concepts', [])):
                    raise DemoError('Proposal invented an ontology concept')
                matching = next((existing for existing in draft['definition']['metrics']
                    if not existing.get('filters') and sqlglot.parse_one(existing['expression']).sql() == tree.sql()), None)
                fallback = {'unit': matching['unit'] if matching else 'unspecified',
                    'grain': matching['grain'] if matching else f'Aggregate over {dataset} source records',
                    'time_rule': matching['time_rule'] if matching else 'No date filter; confirm the reporting period',
                    'evidence_refs': [f'table:{dataset}'],
                    'rationale': 'Proposer generated this candidate from source schema and profile.',
                    'assumptions': ['Unspecified metadata requires human confirmation.']}
                for key in ('unit', 'grain', 'time_rule'):
                    if not metadata.get(key):
                        metadata[key] = fallback[key]
                metadata['assumptions'] = list(metadata.get('assumptions', fallback['assumptions'])) + ['LLM-generated candidate; business aggregation and inclusion rules require human review.']
                if isinstance(tree, exp.Sum) and re.search(r'temperature|kelvin|rpm|torque|tool.?wear|percentage|percent|rate|cumulative', tree.sql(), re.I):
                    warnings.append(f'{name}: SUM over a potentially nonadditive measure requires business review.')
                table_profile = profile['tables'].get('source.' + dataset, {}).get('stats', {}).get('columns', {})
                mixed_currency = any('currency' in column.lower() and stats.get('ndv', 0) > 1
                                     for column, stats in table_profile.items())
                amount_columns = [column.name for column in tree.find_all(exp.Column)]
                if isinstance(tree, exp.Sum) and mixed_currency and any(
                    re.search(r'amount|price|paid|balance|cost|revenue', column, re.I)
                    and not re.search(r'_(sgd|usd|eur|gbp|base)$', column, re.I)
                    for column in amount_columns
                ):
                    warnings.append(f'{name}: source rows contain multiple currencies; require a currency group, explicit currency filter, or verified FX conversion rule before approval.')
                if matching:
                    for key in ('unit', 'grain', 'time_rule', 'inclusion_rules', 'exclusion_rules'):
                        if matching.get(key):
                            metadata[key] = matching[key]
                    for key in ('synonyms', 'example_questions', 'ontology_concepts', 'evidence_refs', 'assumptions'):
                        metadata[key] = list(dict.fromkeys(matching.get(key, []) + metadata.get(key, [])))
                    if matching.get('owner'):
                        metadata['owner'] = matching['owner']
                    if name != matching['name'] or m['description'] != matching['description']:
                        warnings.append(f"{matching['name']}: preserved declared name and business description for the exact source formula; raw LLM wording remains in proposer_output.")
                    name = matching['name']
                value['metrics'].append(dict(**(fallback | metadata), id=matching.get('id', '') if matching else known.get(name, ''), name=name,
                    description=matching['description'] if matching else m['description'] or name, expression=tree.sql(),
                    reference_sql='', dimensions=[], filters=[], confidence=m['confidence']))
            normalized = {sqlglot.parse_one(metric['expression']).sql() for metric in value['metrics']}
            retained = []
            for source_metric in draft['definition']['metrics']:
                source_expression = sqlglot.parse_one(source_metric['expression']).sql()
                if source_metric.get('filters') or source_expression not in normalized:
                    warnings.append(f"Declared metric {source_metric['name']} was not reproduced exactly; retained its source formula and business rules.")
                    for generated in value['metrics']:
                        if generated['name'] == source_metric['name']:
                            generated['name'] = ('proposed_' + generated['name'])[:64]
                            generated['id'] = ''
                            warnings.append(f"LLM changed the inclusion semantics of {source_metric['name']}; renamed the extra candidate for review.")
                    preserved = copy.deepcopy(source_metric)
                    preserved.update(reference_sql='', confidence=None,
                        rationale='Declared source candidate retained separately; the LLM did not reproduce this formula.',
                        assumptions=list(source_metric.get('assumptions', [])) + ['Retained source definition requires explicit human review.'])
                    retained.append(preserved)
            value['metrics'] = retained + value['metrics']
            if len(value['metrics']) > 20:
                raise DemoError('Source-preserving proposal exceeded the 20 metric review limit; draft preserved')
            for ds in proposed['datasets']:
                dataset = ds['table'].removeprefix('source.')
                value['dataset_meanings'][dataset] = ds['description'][:1500]
                for field in ds['fields']:
                    name = dataset + '.' + field['column']
                    if name not in self.workspace._fields:
                        raise DemoError('Proposal invented a field')
                    value['field_roles'][name] = field['role']
                    if field['description']:
                        value['field_meanings'][name] = field['description'][:1000]
        else:
            for metric in value['metrics']:
                metric.update(reference_sql='', confidence=None,
                    evidence_refs=['source:declared_metric', 'profile:source_tables'],
                    rationale='Retained the declared source metric; no LLM inference was performed.',
                    assumptions=['Business meaning and reporting period require human confirmation.'])
        provenance = ProposalProvenance(mode=mode, provider=getattr(llm, 'provider', '') if mode == 'llm' else '',
            model=getattr(llm, 'model', '') if mode == 'llm' else '', generated_at=now(), snapshot_sha256=self.workspace.pack.fingerprint)
        value['proposal_provenance'] = provenance.model_dump()
        definition = ContextDefinition.model_validate(self.workspace.identify(value))
        try:
            self.workspace.build_model(definition)
        except Exception as exc:
            warnings.append('Technical validation required: ' + str(exc))
        proposal = dict(proposal_id=uuid.uuid4().hex, revision=revision, mode=mode,
            label='LLM proposal' if mode == 'llm' else 'Deterministic source evidence draft',
            definition=definition.model_dump(), evidence={'harvest': harvest, 'profile': profile, 'document_coverage': coverage},
            warnings=warnings, provenance=provenance.model_dump(),
            proposer_output=proposed if mode == 'llm' else None)
        proposal['metric_origins'] = {metric['id']: ('declared_source_retained' if metric['rationale'].startswith('Declared source candidate retained separately') or mode == 'evidence' else 'llm_generated') for metric in proposal['definition']['metrics']}
        proposal['candidate_id'] = proposal['proposal_id']
        with self.workspace.connection(write=True) as conn:
            self.workspace._draft(conn, revision)
            conn.execute('CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, content TEXT NOT NULL)')
            conn.execute('INSERT INTO proposals VALUES (?, ?)', (proposal['proposal_id'], canonical(proposal).decode()))
        return proposal

    def apply(self, proposal_id: str, revision: int):
        candidates = self.view()['items']
        proposal = next((p for p in candidates if p['proposal_id'] == proposal_id), None)
        if proposal is None:
            raise DemoError('Proposal not found for this source snapshot')
        if proposal['revision'] != revision:
            raise DemoError('Proposal was generated for another draft revision')
        return self.workspace.save(revision, ContextDefinition.model_validate(proposal['definition']))
