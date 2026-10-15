"""Permission-first lexical retrieval with conservative Ossie dependency closure."""
import copy
import json
import re
from collections import deque
import sqlglot
from sqlglot import exp
from .connectors import ConnectionFailure
from .semantics import digest


class Clarification(ConnectionFailure):pass


def tokens(text):return set(re.findall(r'[a-z0-9]+',text.lower()))-{'show','what','the','is','of','and','by','for','in','a','me'}


def expressions(item):
    return [entry['expression'] for entry in item.get('expression',{}).get('dialects',[])]


def project(item,kind):
    """Only reviewed semantic attributes enter serving output; opaque extensions stay server-side."""
    allowed={'name','description','ai_context'}|{
        'dataset':{'source'}, 'field':{'expression','datatype','label','dimension'},
        'metric':{'expression','datatype'}, 'relationship':{'from','to','from_columns','to_columns'},
    }[kind]
    result={key:copy.deepcopy(value) for key,value in item.items() if key in allowed}
    if 'ai_context' in result:result['ai_context']={'synonyms':result['ai_context'].get('synonyms',[])}
    keys={'dataset':['kind'],'field':['role'],'metric':['dataset'],'relationship':['is_default']}[kind]
    for extension in item.get('custom_extensions',[]):
        if extension.get('vendor_name')!='HELIOS':continue
        try:data=json.loads(extension.get('data','{}'))
        except (ValueError,TypeError):continue
        result['custom_extensions']=[{'vendor_name':'HELIOS','data':json.dumps({key:data[key] for key in keys if key in data})}]
        break
    return result


class SemanticIndex:
    def __init__(self,doc,caller=None):
        self.full=doc;self.caller=caller;self.datasets={d['name']:d for d in doc['datasets']}
        self.fields={(d['name'],f['name']):f for d in doc['datasets'] for f in d['fields']}
        self.sources={d['source']:d['name'] for d in doc['datasets']}
        self.metrics={m['name']:m for m in doc.get('metrics',[])}
        if caller and digest(doc)!=caller.model_sha256:raise ConnectionFailure('The caller scope does not match the active semantic release.')

    def permits(self,key):
        return key in self.fields and (self.caller is None or self.caller.permits(self.datasets[key[0]]['source'],key[1]))

    def resolve(self,ref,default=None):
        parts=ref.rsplit('.',1)
        if len(parts)==2:key=(self.sources.get(parts[0],parts[0]),parts[1])
        elif default:key=(default,ref)
        else:
            matches=[key for key,field in self.fields.items() if self.permits(key) and (key[1]==ref or field.get('label')==ref)]
            if len(matches)!=1:raise ValueError('Ambiguous or missing field')
            key=matches[0]
        if not self.permits(key):raise ValueError('Unavailable field')
        return key

    def dependencies(self,item,default=None):
        result=set()
        for expression in expressions(item):
            if default and expression==item['name']:
                result.add(self.resolve(item['name'],default));continue
            ast=sqlglot.parse_one(expression)
            for column in ast.find_all(exp.Column):
                qualifier='.'.join(part.name for part in column.parts[:-1])
                result.add(self.resolve(qualifier+'.'+column.name if qualifier else column.name,default))
        return result

    def expand(self,keys):
        result=set();pending=list(keys)
        while pending:
            key=pending.pop()
            if key in result:continue
            if not self.permits(key):raise ValueError('Unavailable dependency')
            result.add(key)
            pending.extend(self.dependencies(self.fields[key],key[0])-result)
        return result

    def metric_keys(self,metric):
        extensions=[json.loads(e['data']) for e in metric.get('custom_extensions',[]) if e.get('vendor_name')=='HELIOS']
        ds=next((e.get('dataset') for e in extensions if e.get('dataset')),None)
        ds=self.sources.get(ds,ds)
        if ds is not None and ds not in self.datasets:raise ValueError('Metric has no approved source')
        keys=self.dependencies(metric,ds)
        if not keys or ds is not None:
            if ds is None and len(self.datasets)==1:ds=next(iter(self.datasets))
            if ds not in self.datasets:raise ValueError('Metric has no approved source')
            candidates=[key for key in self.fields if key[0]==ds and self.permits(key)]
            if not candidates:raise ValueError('Unavailable metric source')
            if not any(key[0]==ds for key in keys):keys.add(candidates[0])
        return self.expand(keys)

    def eligible(self):
        fields={}
        for key in self.fields:
            try:fields[key]=self.expand({key})
            except (ValueError,KeyError,TypeError,sqlglot.errors.ParseError):continue
        metrics={}
        for name,metric in self.metrics.items():
            try:metrics[name]=self.metric_keys(metric)
            except (ValueError,KeyError,TypeError,sqlglot.errors.ParseError):continue
        return fields,metrics

    def relations(self):
        result=[]
        for relationship in self.full.get('relationships',[]):
            keys={(relationship['from'],col) for col in relationship['from_columns']}|{(relationship['to'],col) for col in relationship['to_columns']}
            try:self.expand(keys)
            except (ValueError,KeyError,TypeError,sqlglot.errors.ParseError):continue
            result.append(relationship)
        return result

    def authorized_document(self):
        fields,metrics=self.eligible()
        result={'name':self.full['name'],'version':self.full.get('version'),'datasets':[],
                'metrics':[project(self.metrics[name],'metric') for name in metrics],'relationships':[project(rel,'relationship') for rel in self.relations()]}
        for name,dataset in self.datasets.items():
            selected=[project(field,'field') for field in dataset['fields'] if (name,field['name']) in fields]
            if not selected:continue
            clean=project(dataset,'dataset')
            clean['fields']=selected;clean['primary_key']=[field for field in dataset.get('primary_key',[]) if (name,field) in fields]
            result['datasets'].append(clean)
        return result

    def bundle(self,question,max_datasets=5,max_fields=100,max_chars=24000):
        fields,metrics=self.eligible();q=tokens(question);rank=[]
        browse=bool(q & {'definitions','metrics','model','schema'})
        def score(item):
            names=' '.join([item['name'],item.get('label',''),*item.get('ai_context',{}).get('synonyms',[])])
            return 4*len(q & tokens(names))+len(q & tokens(item.get('description','')))
        for name in metrics:
            value=score(self.metrics[name])
            if value:rank.append((value,'metric',name))
        for key in fields:
            dataset_terms=tokens(key[0])
            value=score(self.fields[key])+(2*len(q & dataset_terms) if browse or q<=dataset_terms else 0)
            if value:rank.append((value,'field',key))
        rank.sort(key=lambda entry:(-entry[0],entry[1],str(entry[2])))
        if not rank and browse:
            rank=[(1,'metric',name) for name in sorted(metrics)[:10]] or [(1,'field',key) for key in sorted(fields)[:10]]
        if not rank:raise Clarification('No permitted semantic definition matched. Specify an approved metric, business term or field.')
        metric_hits=[hit for hit in rank if hit[1]=='metric']
        if not browse and len(metric_hits)>1 and metric_hits[0][0]==metric_hits[1][0]:
            choices=[hit[2] for hit in metric_hits if hit[0]==metric_hits[0][0]][:5]
            raise Clarification('Choose an approved metric: '+', '.join(choices)+'. State any required exclusions or time basis.')
        selected=rank[:10];names={hit[2] for hit in selected if hit[1]=='metric'};keys=set()
        for _,kind,key in selected:keys.update(metrics[key] if kind=='metric' else fields[key])
        datasets={key[0] for key in keys};relationships=[];eligible_relations=self.relations()
        if datasets:
            root=sorted(datasets)[0]
            for target in sorted(datasets-{root}):
                queue=deque([(root,[])]);seen={root};path=None
                while queue:
                    current,trail=queue.popleft()
                    if current==target:path=trail;break
                    for rel in eligible_relations:
                        if current not in {rel['from'],rel['to']}:continue
                        other=rel['to'] if rel['from']==current else rel['from']
                        if other not in seen and len(trail)<max_datasets-1:seen.add(other);queue.append((other,trail+[rel]))
                if path is None:raise Clarification('The matching definitions have no permitted join path. Narrow the question to one dataset.')
                for rel in path:
                    alternatives=[candidate for candidate in eligible_relations if {candidate['from'],candidate['to']}=={rel['from'],rel['to']}]
                    if len(alternatives)>1:
                        defaults=[]
                        for candidate in alternatives:
                            extensions=[json.loads(e['data']) for e in candidate.get('custom_extensions',[]) if e.get('vendor_name')=='HELIOS']
                            if any(e.get('is_default') for e in extensions):defaults.append(candidate)
                        if len(defaults)!=1:raise Clarification('Multiple permitted relationships connect the selected datasets. Specify the approved relationship before querying.')
                        rel=defaults[0]
                    if rel not in relationships:relationships.append(rel)
                    keys.update(self.expand({(rel['from'],col) for col in rel['from_columns']}|{(rel['to'],col) for col in rel['to_columns']}))
        datasets={key[0] for key in keys}
        # Keep required keys but never widen to every field in a matching table.
        for ds in list(datasets):
            keys.update(self.expand({(ds,key) for key in self.datasets[ds].get('primary_key',[]) if self.permits((ds,key))}))
        datasets={key[0] for key in keys}
        bundle={'version':self.full.get('version'),'name':self.full['name'],'datasets':[],
                'metrics':[project(self.metrics[name],'metric') for name in sorted(names)],'relationships':[project(rel,'relationship') for rel in relationships]}
        for name in sorted(datasets):
            d=self.datasets[name]
            clean=project(d,'dataset')
            clean['fields']=[project(f,'field') for f in d['fields'] if (name,f['name']) in keys]
            clean['primary_key']=[key for key in d.get('primary_key',[]) if (name,key) in keys]
            bundle['datasets'].append(clean)
        size=len(json.dumps(bundle))
        if len(datasets)>max_datasets or len(keys)>max_fields or size>max_chars:
            raise Clarification('Required semantic dependencies exceed the context budget. Narrow the metric, dataset or business scope.')
        evidence={'release_sha256':digest(self.full),'policy_revision':self.caller.revision if self.caller else 'single-operator',
                  'sources':[dataset['source'] for dataset in bundle['datasets']],
                  'method':'permission-filtered lexical retrieval','context_chars':size,'dataset_count':len(datasets),'field_count':len(keys),
                  'matches':[{'kind':kind,'name':'.'.join(key) if isinstance(key,tuple) else key,'score':value} for value,kind,key in selected],
                  'limits':{'datasets':max_datasets,'fields':max_fields,'context_chars':max_chars}}
        return bundle,evidence


def validate_request(settings,bundle,request):
    """Use Helios resolution and planning to reject names outside the retrieved bundle."""
    from .semantics import helios_modules
    model_mod,compiler_mod,_=helios_modules(settings.helios_path)
    try:
        if set(request)-{'metrics','measures','dimensions','filters','via','order_by','limit','dataset'}:raise ValueError()
        model=model_mod.SemanticModel(bundle)
        req=compiler_mod.SemanticRequest.from_dict(request)
        compiler_mod.Compiler(model).plan(req)
        if req.dataset and req.dataset not in model.datasets:raise ValueError()
        for ref in req.order_by:
            name=ref.lstrip('-')
            try:model.metric(name)
            except KeyError:model.field(name)
        if any(name not in model.relationships for name in req.via.values()):raise ValueError()
    except Exception:raise ConnectionFailure('The request references definitions outside the retrieved semantic bundle.') from None
