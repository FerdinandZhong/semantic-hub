"""Read-only chat over checked Playground plans, with observable execution stages."""
from __future__ import annotations

import json
import re

from .playground import RunPlan


def retrieval_details(playground, payload, plan):
    """Expose actual ranking measures. Never convert a selected metric into confidence."""
    if plan.get('kind') == 'document':
        query = plan.get('retrieval', {}).get('search_query') or payload.question
        terms = set(re.findall(r'[a-z0-9_]+', query.lower()))
        matches = []
        for passage in plan.get('passages', []):
            text = passage['title'] + ' ' + passage['text'] + ' ' + json.dumps(passage.get('links', []), ensure_ascii=False)
            overlap = len(terms & set(re.findall(r'[a-z0-9_]+', text.lower())))
            matches.append({'name': passage['title'], 'location': passage.get('location'),
                            'score': overlap, 'query_terms': len(terms)})
        return {'method': 'Keyword overlap', 'score_kind': 'matched query terms', 'matches': matches,
                'confidence': None, 'note': 'Keyword matches measure relevance, not answer correctness.'}
    if payload.metric:
        return {'method': 'Saved metric selection', 'score_kind': None, 'matches': [], 'confidence': None,
                'note': 'You selected a published metric directly. No retrieval confidence score applies.'}
    _, scope, model = playground.adopted(payload.version, payload.context_sha256)
    found = playground.retrieval.discover(payload.question, scope)
    matches = next((item['matches'] for item in found if item['model_id'] == model), [])
    return {'method': 'SQLite FTS5 lexical relevance', 'score_kind': 'raw relevance',
            'matches': matches, 'confidence': None,
            'selected_metric': (plan.get('metric') or {}).get('name'),
            'note': 'Raw scores rank matches within this release. They are not probabilities; scope checks determine whether execution is allowed.'}


def answer(playground, payload, llm_factory, emit):
    """Submitting Ask & run authorizes this one bounded, read-only execution."""
    emit('retrieve', 'Read published definitions and find relevant evidence')
    llm = llm_factory() if payload.metric is None else None
    plan = playground.interpret(payload, llm, progress=emit)
    if plan.get('status') != 'ready':
        return plan
    emit('check', 'Check the selected metric, source scope, and execution plan')
    details = retrieval_details(playground, payload, plan)
    emit('retrieval', details)
    emit('execute', 'Read published passages' if plan.get('kind') == 'document' else 'Execute the checked read-only SQL')
    result = playground.execute(RunPlan(pack_id=payload.pack_id, snapshot_sha256=payload.snapshot_sha256,
        session_id=payload.session_id, plan_id=plan['plan_id']), llm=llm, llm_factory=llm_factory, progress=emit)
    emit('answer', 'Prepare the answer with source evidence')
    result['retrieval_details'] = details
    result['metric'] = {k: plan.get('metric', {}).get(k) for k in ('name', 'description', 'unit')}
    result['request'] = plan.get('request')
    return result
