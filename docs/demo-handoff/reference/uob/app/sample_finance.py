"""Explicit offline financial data; no live connector or evaluation labels."""
import hashlib
import json
from datetime import date,datetime
from decimal import Decimal
from pathlib import Path
from threading import Timer
import duckdb
import sqlglot
from .connectors import ConnectionFailure
from .financial_fixture import SCHEMA,generate
from .semantics import validate_sql


def checksum(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(directory,seed=8100,customers=200,transactions=5000):
    """Build once into a new directory; runtime only reads the resulting database."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    bundle=generate(seed,customers,transactions)
    database=directory/'finance.duckdb'
    with duckdb.connect(str(database)) as conn:
        conn.execute('CREATE SCHEMA synthetic_finance')
        for name,columns in SCHEMA.items():
            conn.execute('CREATE TABLE synthetic_finance.'+name+' ('+', '.join(field+' '+kind for field,kind in columns)+')')
            values=[]
            for row in bundle['tables'][name]:
                values.append([Decimal(row[field]) if kind.startswith('decimal') else row[field] for field,kind in columns])
            if values:conn.executemany('INSERT INTO synthetic_finance.'+name+' VALUES ('+','.join('?' for _ in columns)+')',values)
    # Test labels and corrupt records are deliberately absent from this serving artifact.
    manifest={**bundle['manifest'],'database_sha256':checksum(database),
              'rows':{name:len(rows) for name,rows in bundle['tables'].items()},
              'schema_name':'synthetic_finance','catalog':'iceberg'}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
    reference={'total_settled_outflow_sgd':str(sum((Decimal(row['amount_sgd']) for row in bundle['tables']['payments']),Decimal(0))),
               'settled_payment_count':len(bundle['tables']['payments']),
               'by_jurisdiction':{key:str(sum((Decimal(row['amount_sgd']) for row in bundle['tables']['payments'] if row['jurisdiction']==key),Decimal(0))) for key in ['SG','HK','GB']}}
    return manifest,reference


class Finance:
    def __init__(self,settings):
        self.directory=Path(settings.sample_finance_dir)
        try:
            self.manifest=json.loads((self.directory/'manifest.json').read_text())
            self.database=self.directory/'finance.duckdb'
            if self.manifest['schema']!='uob.synthetic.finance.v1' or self.manifest['synthetic'] is not True or checksum(self.database)!=self.manifest['database_sha256']:raise ValueError()
        except (OSError,ValueError,KeyError,TypeError):
            raise ConnectionFailure('Synthetic financial artifact is unavailable or its checksum changed. No live source was queried.') from None

    def connection(self):
        return duckdb.connect(str(self.database),read_only=True,config={'enable_external_access':False,'threads':2,'memory_limit':'256MB'})

    def execute(self,sql,doc):
        """Validate logical source paths before translating their catalog and dialect."""
        try:
            clean=validate_sql(sql,doc)
            ast=sqlglot.parse_one(clean,read='trino')
            for table in ast.find_all(sqlglot.exp.Table):
                if table.catalog!='iceberg' or table.db!='synthetic_finance' or table.name not in SCHEMA:
                    raise ConnectionFailure('The query references a table outside the synthetic financial artifact.')
                table.set('catalog',None)
            for column in ast.find_all(sqlglot.exp.Column):
                if column.catalog:
                    if column.catalog!='iceberg' or column.db!='synthetic_finance':raise ConnectionFailure('Invalid synthetic column scope.')
                    column.set('catalog',None)
            with self.connection() as conn:
                timer=Timer(10,conn.interrupt);timer.daemon=True;timer.start()
                try:
                    cursor=conn.execute(ast.sql(dialect='duckdb'))
                    names=[column[0] for column in cursor.description]
                    rows=cursor.fetchmany(100)
                finally:timer.cancel()
            def value(v):
                if isinstance(v,Decimal):return format(v,'f')
                if isinstance(v,(date,datetime)):return v.isoformat()
                return v
            return [dict(zip(names,map(value,row))) for row in rows]
        except ConnectionFailure:raise
        except Exception:raise ConnectionFailure('The synthetic query could not run within the approved SQL scope.') from None

    def discover(self,request):
        from .metadata_inventory import inventory
        if request.action=='catalogs':return {'mode':'sample','synthetic':True,'items':['iceberg']}
        if request.catalog!='iceberg':raise ConnectionFailure('Unknown synthetic catalog.')
        if request.action=='schemas':return {'mode':'sample','synthetic':True,'items':['synthetic_finance']}
        if request.schema_name!='synthetic_finance':raise ConnectionFailure('Unknown synthetic schema.')
        if request.action=='tables':return {'mode':'sample','synthetic':True,'items':list(SCHEMA)}
        if request.table not in SCHEMA:raise ConnectionFailure('Unknown synthetic table.')
        columns=[{'name':name,'type':kind} for name,kind in SCHEMA[request.table]]
        source='iceberg.synthetic_finance.'+request.table
        result={'mode':'sample','synthetic':True,'source':source,'columns':columns,
                'fixture_sha256':self.manifest['database_sha256'],
                'scope':'Synthetic financial fixture. At most 50 rows are shown; no live source was queried.'}
        result['metadata']=inventory('iceberg','synthetic_finance',request.table,columns,mode='sample')
        if request.action in {'preview','profile'}:
            rows=self.execute('SELECT * FROM '+source+' LIMIT 50',{'datasets':[{'source':source}]})
            if request.action=='preview':result.update(rows=rows,limit=50)
            else:
                result.update(sample_size=len(rows),columns=[{**column,'nulls':sum(row[column['name']] is None for row in rows),
                    'distinct_in_sample':len({str(row[column['name']]) for row in rows})} for column in columns])
        return result
