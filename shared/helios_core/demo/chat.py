"""Read-only chat over checked Playground plans, with observable execution stages."""
from __future__ import annotations

import copy
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


def semantic_canvas(plan):
    """Read-only HeliosCanvas payload: only the objects this plan actually used."""
    graph = copy.deepcopy(plan.get('graph') or {'nodes': [], 'edges': []})
    passages = plan.get('passages') or []
    if passages:
        tables = {n['id'] for n in graph['nodes']}
        graph['nodes'].append({'id': 'evidence:documents', 'type': 'document_group',
                               'label': f'Passages used ({len(passages)})'})
        linked = set()
        for passage in passages:
            graph['nodes'].append({'id': passage['id'], 'type': 'document', 'label': passage['title'],
                                   'location': passage.get('location'), 'citation': passage.get('citation')})
            for link in passage.get('links', []):
                kind, _, name = link['target'].partition(':')
                table = name.split('.')[0] if kind in ('table', 'field') else None
                if table in tables:
                    linked.add(table)
        graph['edges'] += [{'id': f'evidence:group:{t}', 'source': 'evidence:documents', 'target': t,
                            'kind': 'document_evidence', 'label': 'Supporting passages',
                            'document_id': 'evidence:documents'} for t in sorted(linked)]
    if not graph['nodes']:
        return None
    metric = plan.get('metric') or {}
    return {'graph': graph, 'definition': plan.get('graph_definition') or {'metrics': [], 'joins': []},
            'focus': metric.get('id') or ('metric:' + metric['name'] if metric.get('name') else None)}


def _check(name, status, detail):
    return {'name': name, 'status': status, 'detail': detail}


def sql_checks(sql, request, tables):
    """Structural checks on the executed SQL. They verify shape, not business correctness."""
    import sqlglot
    from sqlglot import exp
    tree = sqlglot.parse_one(sql, read='duckdb')
    writes = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Merge)
    read_only = isinstance(tree, (exp.Select, exp.Union)) and not any(tree.find_all(*writes))
    used = {t.name for t in tree.find_all(exp.Table)}
    group = tree.args.get('group')
    grouped = {c.sql(dialect='duckdb') for c in group.find_all(exp.Column)} if group else set()
    where = tree.args.get('where')
    filtered = {c.sql(dialect='duckdb') for c in where.find_all(exp.Column)} if where else set()
    missing = [f['field'] for f in request.get('filters', []) if f['field'] not in filtered]
    return [
        _check('Read-only SELECT', 'pass' if read_only else 'fail', 'Single SELECT statement' if read_only else 'Statement is not a plain SELECT'),
        _check('Tables in published model', 'pass' if used <= tables else 'fail', ', '.join(sorted(used)) or 'No tables'),
        _check('Grouping matches request', 'pass' if grouped == set(request.get('dimensions', [])) else 'fail',
               ', '.join(sorted(grouped)) or 'No grouping'),
        _check('Requested filters applied', 'pass' if not missing else 'fail',
               f"{len(request.get('filters', []))} filter(s)" if not missing else 'Missing: ' + ', '.join(missing)),
        _check('Row limit present', 'pass' if tree.args.get('limit') else 'fail',
               f"Displays up to {request.get('limit')} rows; one extra row detects truncation" if tree.args.get('limit') else 'No LIMIT'),
    ]


def answer_checks(plan, result, details):
    """Deterministic per-answer evaluation. Counts of real checks, never a confidence score."""
    retrieval, generation = [], []
    if plan.get('kind') == 'document' or plan.get('passages'):
        found = plan.get('retrieval', {})
        selected = len(plan.get('passages', []))
        retrieval.append(_check('Passages retrieved', 'pass' if selected else 'fail',
                                f"{selected} of {found.get('candidate_count', selected)} published passages"))
        hits = [m for m in details.get('matches', []) if m.get('score')]
        if details.get('method') == 'Keyword overlap':
            retrieval.append(_check('Passages with keyword overlap', 'pass' if hits else 'warn',
                                    f'{len(hits)} of {len(details["matches"])} (relevance signal)'))
    if plan.get('kind') in ('metric', 'hybrid'):
        if details.get('method') == 'Saved metric selection':
            retrieval.append(_check('Metric retrieval', 'n/a', 'Saved metric selected directly; no retrieval score applies'))
        else:
            ranked = [m['name'] for m in details.get('matches', []) if m.get('kind') == 'metric']
            name = (plan.get('metric') or {}).get('name')
            rank = ranked.index(name) + 1 if name in ranked else None
            retrieval.append(_check('Selected metric rank', 'pass' if rank == 1 else 'warn',
                f'Rank {rank} of {len(ranked)} lexical metric matches (relevance signal)' if rank
                else 'Not among lexical metric matches; chosen by the planner'))
        scope = (plan.get('scope_check') or {}).get('checks', [])
        if scope:
            ok = sum(c['status'] == 'supported' for c in scope)
            retrieval.append(_check('Scope checks', 'pass' if ok == len(scope) else 'fail', f'{ok}/{len(scope)} supported'))
        if result.get('sql'):
            tables = {n['id'] for n in (plan.get('graph') or {}).get('nodes', [])}
            generation += sql_checks(result['sql'], plan['request'], tables)
            rows = len(result.get('rows') or [])
            generation.append(_check('Result returned', 'warn' if result.get('status') == 'no_data' or not rows else 'pass',
                f"{rows} row(s){' · display limit reached' if result.get('truncated') else ''}"))
    verified = result.get('verification')
    if verified:
        generation += [
            _check('Citations verified', 'pass', f"{verified['citations']}/{verified['citations']} quotes found in source text"),
            _check('Numbers grounded', 'pass', f"{verified['numbers']}/{verified['numbers']} numbers appear in cited quotes"),
            _check('Evidence support check', 'pass', f"{verified['claims']} claim(s) passed"),
            _check('Answer repair', 'pass' if verified['attempts'] == 1 else 'warn',
                   'First attempt passed' if verified['attempts'] == 1 else 'Passed after one bounded repair'),
        ]
    elif plan.get('passages'):
        generation.append(_check('Cited answer', 'warn', result.get('message') or 'No cited claims were accepted'))
    scored = [c for c in retrieval + generation if c['status'] != 'n/a']
    return {'retrieval': retrieval, 'generation': generation,
            'summary': {'passed': sum(c['status'] == 'pass' for c in scored), 'total': len(scored)}}


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
    result['semantic_canvas'] = semantic_canvas(plan)
    result['evaluation'] = answer_checks(plan, result, details)
    return result
