"""Render this independent proposal using the repository's diagram drawing utility."""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('diagram_drawing', HERE.parents[1] / 'apps/helios/workbench/architecture_diagrams.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.OUT = HERE

def build():
    d = m.Diagram('agent-workflow',1740,1480,'Self-service data transformation',
                  'Consolidate business logic into reviewed PySpark pipelines, governed Hive tables, and parallel CSV outputs.')
    brand='INDEPENDENT USE CASE  /  PROPOSED DESIGN'
    d.root.find("mxCell[@id='brand']").set('value',brand)
    d.svg=[s.replace('SEMANTIC HUB  /  IMPLEMENTED ARCHITECTURE',brand) for s in d.svg]
    def box(i,x,y,title,lines,kind=None,fill='white'):
        d.card(i,x,y,500,155,title,lines,tag=kind,fill=fill,size=19)
    box('input',60,200,'Business uploads',['CSV files + MySQL / Excel logic','Restricted landing area; no direct LLM access'])
    box('privacy',620,200,'IT intake and privacy gate',['IT creates intake DDL + Atlas PII tags','Only approved, sanitized context reaches AI'],fill='#FFF3DF')
    box('coordinator',1180,200,'Workflow coordinator',['Tracks dependencies, artifacts, and approvals','Routes retries; binds execution to approved version'],fill='#EDF3FF')
    d.edge('intake','input','privacy',[(560,277),(620,277)])
    d.edge('admit','privacy','coordinator',[(1120,277),(1180,277)])
    box('mapper',60,470,'Mapper / Interpreter',['Resolve schemas, paths, and dependencies','Define output contracts'],kind='AGENT 1')
    box('converter',620,470,'SQL / Excel Converter',['Merge common logic → fewer PySpark jobs','Example target: 15 scripts → 4'],kind='AGENT 2',fill='#EDF3FF')
    box('creator',1180,470,'Folder / Table Structure Creator',['Plan /input, /output, /tables paths','Generate Hive external-table DDL for IT'],kind='AGENT 3')
    d.edge('coordinate','coordinator','mapper',[(1430,355),(1430,415),(310,415),(310,470)])
    d.edge('map-convert','mapper','converter',[(560,547),(620,547)])
    d.edge('convert-create','converter','creator',[(1120,547),(1180,547)])
    box('validator',1180,740,'Validator',['Check code, schema, and equivalent results','Use sanitized fixtures in an isolated test'],kind='AGENT 4')
    box('documenter',620,740,'Documenter',['Explain consolidation, tests, and lineage','Produce a versioned execution report'],kind='AGENT 5')
    box('human',60,740,'Business review and sign-off',['Review proposed changes and output contract','Approve the exact artifact version'],fill='#FFF3DF')
    d.edge('create-validate','creator','validator',[(1430,625),(1430,740)])
    d.edge('validate-document','validator','documenter',[(1180,817),(1120,817)])
    d.edge('document-review','documenter','human',[(620,817),(560,817)])
    d.edge('feedback','human','mapper',[(150,740),(150,625)],True)
    d.text('feedback-label','Feedback / revise',175,672,300,25,18,m.BLUE)
    d.edge('test-retry','validator','converter',[(1180,775),(1150,775),(1150,665),(870,665),(870,625)],True)
    d.text('retry-label','Failed checks → revise',740,690,340,25,18,m.BLUE)
    box('it',60,1030,'IT executes approved DDL',['Create Hive tables; confirm Atlas PII tags','Grant runtime access after governance checks'],fill='#FFF3DF')
    box('executor',620,1030,'Executor',['Require business approval + IT readiness','Run the approved PySpark pipeline'],kind='AGENT 6')
    box('outputs',1180,1030,'Parallel delivery',['Hive external tables + downstream CSVs','Retain PySpark scripts and run evidence'],fill='#F0F8F3')
    d.edge('business-it','human','it',[(310,895),(310,1030)])
    d.edge('it-executor','it','executor',[(560,1107),(620,1107)])
    d.edge('execute-output','executor','outputs',[(1120,1107),(1180,1107)])
    d.rect('reconcile',620,1270,1060,80,fill='#F0F8F3')
    d.text('reconcile-title','Reconcile legacy CSVs ↔ new CSVs ↔ Hive tables → business-approved cutover',642,1292,1016,32,23,m.INK,True)
    d.edge('parallel-check','outputs','reconcile',[(1430,1185),(1430,1270)])
    d.footer(['Orange boxes: human / IT gates. Dashed arrows: feedback before execution. The coordinator manages all six agents.',
              'Raw PII stays outside LLM prompts. Atlas classification informs an enforced masking / access policy; tags alone do not block access.'])
    return d

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chromium');args=p.parse_args()
    print(build().save(args.chromium))
