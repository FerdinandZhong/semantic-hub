"""Published Ossie models: metadata storage is separate from query execution."""
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
import yaml
from .connectors import ConnectionFailure


def digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_model(settings):
    if settings.alloydb_dsn:
        if not settings.semantic_id or not settings.semantic_version:
            raise ConnectionFailure('Set SEMANTIC_MODEL_ID and SEMANTIC_MODEL_VERSION to an approved release.')
        try:
            import psycopg
            with psycopg.connect(settings.alloydb_dsn, connect_timeout=8, options='-c statement_timeout=8000 -c default_transaction_read_only=on') as conn:
                row = conn.execute('SELECT document, content_sha256 FROM ai_semantic_models WHERE model_id=%s AND release_version=%s AND approval_status=%s', (settings.semantic_id, settings.semantic_version, 'approved')).fetchone()
            if not row:
                raise ConnectionFailure('Approved semantic release not found in AlloyDB.')
            doc, expected = row
        except ConnectionFailure:
            raise
        except Exception:
            raise ConnectionFailure('Cannot read the AlloyDB semantic registry. Check connection and schema setup.') from None
    elif settings.semantic_file:
        path = Path(settings.semantic_file)
        try:
            doc = yaml.safe_load(path.read_text())
        except Exception:
            raise ConnectionFailure('Cannot read the configured Ossie JSON/YAML file.') from None
        expected = settings.semantic_sha
        if not expected or not settings.semantic_version:
            raise ConnectionFailure('Pin the approved file with SEMANTIC_MODEL_SHA256 and SEMANTIC_MODEL_VERSION.')
    else:
        raise ConnectionFailure('No approved Helios model configured. Set a pinned file or AlloyDB registry connection.')
    if digest(doc) != expected:
        raise ConnectionFailure('Semantic release checksum mismatch; publication review required.')
    if not isinstance(doc, dict) or not doc.get('name') or not isinstance(doc.get('datasets'), list):
        raise ConnectionFailure('Invalid Ossie document shape.')
    try:
        for dataset in doc['datasets']:
            if not isinstance(dataset['name'],str) or not isinstance(dataset['source'],str) or not isinstance(dataset['fields'],list):raise ValueError()
            for field in dataset['fields']:
                if not isinstance(field['name'],str):raise ValueError()
        for metric in doc.get('metrics',[]):
            if not isinstance(metric['name'],str) or not isinstance(metric['expression'],dict):raise ValueError()
        for relationship in doc.get('relationships',[]):
            for key in ['name','from','to']:
                if not isinstance(relationship[key],str):raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise ConnectionFailure('Invalid Ossie definitions. Check dataset, field, metric and relationship structure.') from None
    return doc


def describe(doc, version):
    rows = []
    for d in doc.get('datasets', []):
        rows.append({'type':'dataset', 'name':d['name'], 'definition':d.get('description',''), 'source':d.get('source','')})
        for f in d.get('fields', []):
            rows.append({'type':'dimension' if 'dimension' in f else 'field', 'name':d['name']+'.'+f['name'], 'definition':f.get('description',''), 'source':f.get('label',f['name'])})
    for m in doc.get('metrics', []):
        rows.append({'type':'metric', 'name':m['name'], 'definition':m.get('description',''), 'source': json.dumps(m.get('expression',{}))})
    for r in doc.get('relationships', []):
        rows.append({'type':'relationship','name':r['name'],'definition':r['from']+' → '+r['to'],'source':', '.join(r.get('from_columns',[]))})
    return {'rows':rows, 'source':'Approved Helios / Ossie model', 'query':'Describe published semantic definitions', 'scope':f"{doc['name']} · release {version} · sha256 {digest(doc)[:12]}", 'model':{'name':doc['name'],'release':version,'sha256':digest(doc)}}


def helios_modules(path):
    shared = Path(path).expanduser() / 'shared'
    if not path or not (shared/'helios_core').is_dir():
        raise ConnectionFailure('Set HELIOS_PATH to the reviewed Helios checkout to enable semantic compilation.')
    cached=sys.modules.get('helios_core.ossie.model')
    if cached and not Path(cached.__file__).resolve().is_relative_to(shared.resolve()):
        raise ConnectionFailure('Helios checkout changed. Restart the application before using a different compiler checkout.')
    if str(shared) not in sys.path:sys.path.insert(0,str(shared))
    try:
        return (importlib.import_module('helios_core.ossie.model'), importlib.import_module('helios_core.compiler.compiler'), importlib.import_module('helios_core.ossie.build'))
    except ImportError:
        raise ConnectionFailure('Helios compiler dependencies are missing. Follow the demo installation guide.') from None


def validate_sql(sql, doc):
    import sqlglot
    from sqlglot import exp
    statements = sqlglot.parse(sql, read='trino')
    if len(statements)!=1 or not isinstance(statements[0],exp.Select):
        raise ConnectionFailure('Only a single compiled SELECT is permitted.')
    ast = statements[0]
    # No subqueries, table functions or unreviewed table paths in this small demo.
    if len(list(ast.find_all(exp.Select))) != 1:
        raise ConnectionFailure('Nested queries are outside the demo query scope.')
    allowed = {str(d['source']).lower() for d in doc['datasets']}
    for table in ast.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise ConnectionFailure('Table functions are not permitted.')
        name = '.'.join(part.name for part in table.parts).lower()
        if name not in allowed:
            raise ConnectionFailure('Query references a source outside the approved semantic model.')
    # Semantic expressions are trusted only after review; block arbitrary external/UDF calls too.
    allowed_functions = {'sum','avg','min','max','count','coalesce','round','abs','cast','trycast','nullif','case','if'}
    for func in ast.find_all(exp.Func):
        name = func.name.lower() if isinstance(func,exp.Anonymous) else func.sql_name().replace('_','').lower()
        if name not in allowed_functions:
            raise ConnectionFailure('A semantic function is outside the demo allowlist: '+name)
    limit=ast.args.get('limit')
    requested=int(limit.expression.this) if limit and isinstance(limit.expression,exp.Literal) else 100
    return ast.limit(max(1,min(requested,100))).sql(dialect='trino')


def compile_query(settings, doc, request):
    model_mod, compiler_mod, build_mod = helios_modules(settings.helios_path)
    try:
        if build_mod.validate(doc):
            raise ValueError("Ossie validation failed")
        clean = dict(request)
        clean['limit'] = min(int(clean.get('limit') or 100),100)
        if clean['limit'] < 1:raise ValueError('limit')
        allowed = {'metrics','measures','dimensions','filters','via','order_by','limit','dataset'}
        if set(clean)-allowed:raise ValueError('Unknown semantic keys')
        req = compiler_mod.SemanticRequest.from_dict(clean)
        compiled = compiler_mod.Compiler(model_mod.SemanticModel(doc)).compile(req,dialect='trino')
        return validate_sql(compiled.sql,doc)
    except ConnectionFailure:
        raise
    except Exception:
        raise ConnectionFailure('Cannot compile this request against the approved model. Check metric, field and relationship names.') from None


def execute_trino(settings, sql):
    if not settings.trino_host or not settings.trino_user:
        raise ConnectionFailure('Set TRINO_HOST and TRINO_USER for live Iceberg queries.')
    if settings.trino_password and settings.trino_scheme != 'https':
        raise ConnectionFailure('Password authentication to Trino requires HTTPS.')
    try:
        import trino
        from trino.auth import BasicAuthentication
        from trino.transaction import IsolationLevel
        conn = trino.dbapi.connect(host=settings.trino_host,port=settings.trino_port,user=settings.trino_user,catalog=settings.trino_catalog,schema=settings.trino_schema,http_scheme=settings.trino_scheme,auth=BasicAuthentication(settings.trino_user,settings.trino_password) if settings.trino_password else None,verify=settings.ca_bundle or True,request_timeout=10,max_attempts=1,session_properties={'query_max_run_time':'15s'},isolation_level=IsolationLevel.AUTOCOMMIT)
        cursor=conn.cursor()
        try:
            cursor.execute(sql)
            names=[c[0] for c in cursor.description]
            return [dict(zip(names,row)) for row in cursor.fetchmany(100)]
        finally:
            cursor.cancel()
            conn.close()
    except Exception:
        raise ConnectionFailure('Trino query failed. Verify the read-only account, connector, source mappings and engine query limits.') from None
