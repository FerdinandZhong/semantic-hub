"""Small, explicit offline question grammar; unsupported meanings require clarification."""
import re
from .contracts import Plan
from .semantic_retrieval import Clarification

COUNTRIES={'sg':'SG','singapore':'SG','hk':'HK','hong kong':'HK','gb':'GB','uk':'GB','united kingdom':'GB'}


def retrieval_question(question):
    extra=[]
    if re.search(r'\b(?:in|for)\s+(?:SG|HK|GB|UK|Singapore|Hong Kong|United Kingdom)\b',question,re.I):extra.append('jurisdiction')
    if re.search(r'\d{4}-\d{2}-\d{2}',question):extra.append('booking_date')
    if re.search(r'\b(how many|count|number of)\b',question,re.I):extra.append('transaction_id')
    return question+' '+' '.join(extra)


def plan(question,doc):
    text=question.lower().strip()
    if any(re.search(r'\b'+word+r'\b',text) for word in ['delete','update','drop','insert','truncate','attach','install','export']):
        raise Clarification('Sample banking supports read-only questions. No operational action was executed.')
    if re.search(r'\b(explain|definitions|metrics|datasets|relationships|schema)\b',text):return Plan(tool='semantic_describe')
    if re.search(r'\b(net|returns|refunds|average|median|predict|forecast|yesterday|today|excluding|except|without|where|before|after|above|below|over|under|greater|less|last|this|top|bottom|usd|hkd|eur)\b',text):
        raise Clarification('This sample supports reviewed payment totals and counts. Specify an approved definition and explicit dates.')
    words=set(re.findall(r'[a-z_]+',re.sub(r'\b\d{4}-\d{2}-\d{2}\b','',text)))
    allowed=set('what is the show me total sum value amount outflow settled outward payment payments in sgd how many count number of are there by per jurisdiction booking date booking_date customer customer_id identifier between and for sg hk gb uk singapore hong kong united kingdom'.split())
    remainder=re.sub(r'\b\d{4}-\d{2}-\d{2}\b','',text)
    if words-allowed or re.search(r'\d',remainder):
        raise Clarification('This offline grammar cannot represent every condition in your question. Use the shown sample questions.')
    count=bool(re.search(r'\b(how many|count|number of)\b',text))
    if not count and not re.search(r'\b(total|sum|value|amount|outflow)\b',text):
        raise Clarification('Ask for total settled outflow or payment count, optionally by jurisdiction or booking date.')
    if len(doc['datasets'])!=1 or doc['datasets'][0]['source']!='iceberg.synthetic_finance.payments':
        raise Clarification('Select a reviewed synthetic payments model for this walkthrough.')
    fields={f['name']:d['name']+'.'+f['name'] for d in doc['datasets'] for f in d['fields']}
    request={'limit':100,'dimensions':[],'filters':[]}
    if count:
        if 'transaction_id' not in fields:raise Clarification('The selected model does not include a transaction identifier for payment counts.')
        request['measures']=[{'field':fields['transaction_id'],'agg':'count','alias':'settled_payment_count'}]
    else:
        metrics=doc.get('metrics',[])
        if len(metrics)!=1:raise Clarification('Specify one approved payment metric.')
        import sqlglot
        from sqlglot import exp
        expression=metrics[0].get('expression',{}).get('dialects',[{}])[0].get('expression','')
        parsed_expression=sqlglot.parse_one(expression)
        if not isinstance(parsed_expression,exp.Sum) or not isinstance(parsed_expression.this,exp.Column) or parsed_expression.this.name!='amount_sgd':raise Clarification('The selected metric is not a payment total. Select a reviewed sum metric or ask for a count.')
        request['metrics']=[metrics[0]['name']]
    def field(name):
        if name not in fields:raise Clarification('The requested grouping or filter is outside the retrieved model. Specify its approved field name.')
        return fields[name]
    grouping=re.search(r'\b(?:by|per)\s+(.+)',text)
    if len(re.findall(r'\b(?:by|per)\b',text))>1:
        raise Clarification('Specify one supported grouping.')
    if grouping:
        phrase=grouping.group(1)
        if not re.match(r'^(jurisdiction|booking date|booking_date|customer identifier|customer_id|customer)(?:[?.]*$| (?:in|for|between)\b)',phrase):
            raise Clarification('Specify one supported grouping, with an optional jurisdiction or date filter.')
        name='jurisdiction' if phrase.startswith('jurisdiction') else 'booking_date' if phrase.startswith(('booking date','booking_date')) else 'customer_id' if phrase.startswith(('customer','customer_id')) else None
        if not name:raise Clarification('Supported sample groupings are jurisdiction, booking date and customer identifier.')
        request['dimensions']=[field(name)];request['order_by']=[field(name)]
    country=re.search(r'\b(?:in|for)\s+(sg|hk|gb|uk|singapore|hong kong|united kingdom)\b',text)
    mentioned={COUNTRIES[value] for value in re.findall(r'\b(sg|hk|gb|uk|singapore|hong kong|united kingdom)\b',text)}
    if len(mentioned)>1 or (mentioned and not country):
        raise Clarification('Specify one jurisdiction using in SG, in HK or in GB.')
    if country:
        if re.search(r'\b(?:and|or)\s+(sg|hk|gb|uk|singapore|hong kong|united kingdom)\b',text):raise Clarification('Specify one jurisdiction or group results by jurisdiction.')
        request['filters'].append({'field':field('jurisdiction'),'op':'=','value':COUNTRIES[country.group(1)]})
    elif re.search(r'\b(?:in|for)\s+(?!SGD\b)[a-z]+',question,re.I):
        raise Clarification('Specify a supported jurisdiction: SG, HK or GB.')
    dates=re.findall(r'\b\d{4}-\d{2}-\d{2}\b',text)
    if 'between' in words and not dates:
        raise Clarification('Specify two valid dates for the booking-date range.')
    if dates:
        from datetime import date
        try:parsed=[date.fromisoformat(value) for value in dates]
        except ValueError:raise Clarification('Specify valid dates in YYYY-MM-DD format.') from None
        if len(dates)!=2 or 'between' not in text or parsed[0]>parsed[1]:raise Clarification('Specify an inclusive booking-date range using between YYYY-MM-DD and YYYY-MM-DD.')
        request['filters'].append({'field':field('booking_date'),'op':'between','value':dates})
    return Plan(tool='semantic_query',semantic=request)
