"""Independent checks of explicit question periods against immutable source rows.

Cohort boundaries are exact pairs, not overlapping date ranges. This module never
accepts rewritten question text from the model and never substitutes a period.
"""
from __future__ import annotations

import re
import sqlglot
from sqlglot import exp

YEAR = r'(?:19|20)\d{2}'
RANGE = re.compile(rf'(?<!\d)({YEAR})\s*(?:年\s*)?(?:[-–—~至到]|to\b|through\b|and\b)\s*({YEAR})(?!\d)', re.I)


def requirements(question):
    pairs = [list(map(int, m.groups())) for m in RANGE.finditer(question)]
    years = list(dict.fromkeys(int(y) for y in re.findall(rf'(?<!\d)({YEAR})(?!\d)', question)))
    dates = re.findall(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)', question)
    return {'original_question': question, 'year_ranges': pairs, 'years': years, 'dates': dates, 'relative': bool(re.search(r'\b(yesterday|today|last (?:month|year|week)|this (?:month|year|week)|recent|latest)\b|昨天|今天|上个?月|去年|最近', question, re.I))}


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def coverage(runtime, metric):
    """Read only tables actually referenced by the reviewed metric expression."""
    tree = sqlglot.parse_one(metric['expression'], read='duckdb')
    names = {col.table for col in tree.find_all(exp.Column) if col.table}
    # Reviewed dimensions can carry the time axis for a count/star expression.
    if not names:
        names = {f.split('.')[0] for f in metric.get('dimensions', [])}
    observed = []
    for table in runtime.pack.tables:
        if table.name not in names:
            continue
        columns = dict(table.columns)
        if {'period_start', 'period_end'} <= columns.keys():
            result = runtime.query_local(f'SELECT DISTINCT "period_start", "period_end" FROM {ident(table.name)}', limit=201)
            observed.append({'table': table.name, 'kind': 'cohort',
                             'fields': [f'{table.name}.period_start', f'{table.name}.period_end'],
                             'periods': [list(row) for row in result.rows], 'truncated': len(result.rows) > 200})
        else:
            for name, datatype in table.columns:
                if datatype.upper() != 'DATE':
                    continue
                result = runtime.query_local(f'SELECT MIN({ident(name)}), MAX({ident(name)}) FROM {ident(table.name)}')
                observed.append({'table': table.name, 'kind': 'date', 'field': f'{table.name}.{name}',
                                 'minimum': str(result.rows[0][0]) if result.rows[0][0] is not None else None,
                                 'maximum': str(result.rows[0][1]) if result.rows[0][1] is not None else None})
    return observed


def check_scope(runtime, metric, question, filters):
    """Return checked coverage and mandatory filters; fail closed on ambiguous axes."""
    req = requirements(question)
    observed = coverage(runtime, metric)
    result = {'status': 'supported', 'requirements': req, 'coverage': observed,
              'filters': list(filters), 'message': 'The requested period matches the checked source coverage.'}
    chinese = bool(re.search(r'[\u4e00-\u9fff]', question))
    def stop(status, english, zh):
        return result | {'status': status, 'message': zh if chinese else english}
    if req['relative']:
        return stop('needs_clarification', 'Specify explicit dates for this snapshot. Relative periods are ambiguous.', '请指定明确日期。此快照中的相对时间范围不明确。')
    if not req['years']:
        result['message'] = 'No explicit year requested. The selected source snapshot supplies the scope.'
        return result
    cohorts = [c for c in observed if c['kind'] == 'cohort']
    if cohorts:
        if len(req['year_ranges']) != 1 or len(req['years']) != 2 or req['dates']:
            return stop('needs_clarification', 'Specify one launch cohort as a start year and end year. Launch period, sales year, and report year are different.', '请明确一个上市年份区间。上市区间、销售年份和报告年份不是同一时间口径。')
        requested = req['year_ranges'][0]
        if requested[0] > requested[1]:
            return stop('needs_clarification', 'The start year is after the end year.', '起始年份晚于结束年份。')
        for c in cohorts:
            pairs = [[int(a), int(b)] for a,b in c['periods'] if a is not None and b is not None and str(a).isdigit() and str(b).isdigit()]
            if requested not in pairs:
                available = ', '.join(f'{a}–{b}' for a,b in pairs[:10]) or 'none'
                return stop('needs_clarification' if c['truncated'] else 'no_data',
                    f'No matching cohort data for {requested[0]}–{requested[1]}. Checked {c["table"]}; available cohorts: {available}. No other period was substituted.',
                    f'没有 {requested[0]}–{requested[1]} 年区间的数据。已检查 {c["table"]}；可用区间：{available}。未替换为其他年份。')
            for field, value in zip(c['fields'], requested):
                # Original question wins even if AI supplied another period.
                result['filters'] = [f for f in result['filters'] if f['field'] != field]
                result['filters'].append({'field': field, 'op': '=', 'value': value})
        return result
    dated = [c for c in observed if c['kind'] == 'date']
    if len(dated)>1:
        named = [c for c in dated if c['field'].split('.')[-1].replace('_',' ') in question.lower() or c['field'] in question]
        if len(named)==1: dated=named
    if len(dated) == 1:
        c = dated[0]
        if not c['minimum'] or not c['maximum']:
            return stop('no_data', 'No dated records exist for this metric in the selected snapshot.', '所选快照中没有此指标的日期记录。')
        start, end = (req['dates'][0], req['dates'][-1]) if req['dates'] else (f'{min(req["years"])}-01-01', f'{max(req["years"])}-12-31')
        if start > end or end < c['minimum'] or start > c['maximum']:
            return stop('no_data', f'No data for the requested period. {c["field"]} covers {c["minimum"]} to {c["maximum"]}.', f'所请求的时间段没有数据。{c["field"]} 的数据范围为 {c["minimum"]} 至 {c["maximum"]}。')
        if (len(req['years']) > 1 or req['dates']) and (start < c['minimum'] or end > c['maximum']):
            return stop('no_data', f'The snapshot cannot cover the complete requested interval. Available dates: {c["minimum"]} to {c["maximum"]}.', f'快照无法覆盖完整请求区间。可用日期：{c["minimum"]} 至 {c["maximum"]}。')
        # Intersect a requested year with the observed snapshot; report coverage.
        result['filters'] = [f for f in result['filters'] if f['field'] != c['field']]
        result['filters'] += [{'field': c['field'], 'op': '>=', 'value': start}, {'field': c['field'], 'op': '<=', 'value': end}]
        return result
    return stop('needs_clarification', 'This metric has no unambiguous typed time axis for the requested years. Specify a supported metric and time field.', '此指标没有可明确匹配所请求年份的类型化时间字段。请明确指标及时间字段。')


def fixed_values(metric):
    """Conservative fixed population constraints from CASE expressions and explicit filters."""
    choices={}
    tree=sqlglot.parse_one(metric['expression'],read='duckdb')
    for case in tree.find_all(exp.Case):
        if case.args.get('default') and not isinstance(case.args['default'],exp.Null):
            continue
        for branch in case.args.get('ifs',[]):
            condition=branch.this
            if list(condition.find_all(exp.Or)):continue
            for eq in condition.find_all(exp.EQ):
                if isinstance(eq.this,exp.Column) and isinstance(eq.expression,exp.Literal):
                    choices.setdefault(eq.this.sql(),set()).add(str(eq.expression.this))
    for item in metric.get('filters',[]):
        if item.get('op')=='=':choices.setdefault(item['field'],set()).add(str(item['value']))
    return {field:sorted(values) for field,values in choices.items() if len(values)==1}


def check_query_scope(runtime,metric,question,filters):
    """Report independent temporal and categorical checks, without inventing a cause for NULL."""
    temporal=check_scope(runtime,metric,question,filters)
    checks=[{'dimension':'period','status':temporal['status'],'message':temporal['message']}]
    fixed=fixed_values(metric)
    table_fields={t.name:dict(t.columns) for t in runtime.pack.tables}
    for item in filters:
        if item.get('op')!='=' or not isinstance(item.get('value'),str):continue
        field=item['field'];table,_,column=field.partition('.')
        if table_fields.get(table,{}).get(column,'').upper() not in ('VARCHAR','TEXT'):continue
        dimension='geography' if any(word in column.lower() for word in ('geography','country','region','jurisdiction')) else 'category'
        rows=runtime.query_local(f'SELECT DISTINCT {ident(column)} FROM {ident(table)}',limit=101).rows
        values=[r[0] for r in rows];complete=len(values)<=100
        conflict=field in fixed and str(item['value']) not in fixed[field]
        missing=complete and item['value'] not in values
        status='unsupported_scope' if conflict else 'no_data' if missing else 'supported' if item['value'] in values else 'not_checked'
        if conflict:
            message=f"Geography mismatch: " if dimension=='geography' else 'Category mismatch: '
            message+=f"the question requests {item['value']}, but {metric['name']} fixes {field} to {fixed[field][0]}. A filter cannot change that definition."
        elif missing:
            message=f"No {item['value']} records were found in {field} for this snapshot."
        elif status=='supported':message=f"{item['value']} exists in {field}."
        else:message=f"The bounded category inspection does not establish availability of {item['value']} in {field}."
        checks.append({'dimension':dimension,'field':field,'requested':item['value'],'status':status,'message':message,
                       'fixed_values':fixed.get(field,[]),'observed_values':values[:100],'truncated':not complete})
    blocked=[c for c in checks if c['status'] in ('unsupported_scope','no_data','needs_clarification')]
    if not blocked:return temporal|{'checks':checks}
    status='unsupported_scope' if any(c['status']=='unsupported_scope' for c in blocked) else blocked[0]['status']
    messages=[c['message'] for c in blocked]
    if temporal['status']=='supported' and any(c['dimension']!='period' for c in blocked):
        messages.append(temporal['message'])
    return temporal|{'status':status,'message':' '.join(messages),'checks':checks,
                     'reason_dimensions':list(dict.fromkeys(c['dimension'] for c in blocked))}
