"""Generate matching editable draw.io, SVG, and PNG architecture diagrams.

Run with --all to refresh the overview, Playground, and technical views.
No model calls, network requests, or workspace state changes are performed.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/diagrams'
INK, MUTED, BLUE = '#14243B', '#52647A', '#245EDB'
BORDER, BG = '#CCD7E4', '#F5F8FC'


class Diagram:
    def __init__(self, name, width, height, title, subtitle):
        self.name, self.width, self.height = name, width, height
        self.mx = ET.Element('mxfile', host='app.diagrams.net', type='device')
        diagram = ET.SubElement(self.mx, 'diagram', id=name, name=title)
        model = ET.SubElement(diagram, 'mxGraphModel', dx=str(width), dy=str(height), grid='1',
                              gridSize='10', page='1', pageScale='1', pageWidth=str(width),
                              pageHeight=str(height), math='0', shadow='0')
        self.root = ET.SubElement(model, 'root')
        ET.SubElement(self.root, 'mxCell', id='0')
        ET.SubElement(self.root, 'mxCell', id='1', parent='0')
        self.bounds, self.texts, self.connections = {}, [], []
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
                    f'<title>{html.escape(title)}</title><desc>{html.escape(subtitle)}</desc>',
                    '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 Z" fill="#245EDB"/></marker></defs>',
                    f'<rect width="{width}" height="{height}" fill="{BG}"/>']
        self.text('brand', 'SEMANTIC HUB  /  IMPLEMENTED ARCHITECTURE', 50, 24, width-100, 24, 16, BLUE, True)
        self.text('title', title, 50, 62, width-100, 50, 36, INK, True)
        self.text('subtitle', subtitle, 50, 119, width-100, 30, 19, MUTED)

    def rect(self, ident, x, y, w, h, fill='white', stroke=BORDER, dash=False, radius=12):
        assert ident not in self.bounds, ident
        self.bounds[ident] = (x, y, w, h)
        cell = ET.SubElement(self.root, 'mxCell', id=ident, value='', vertex='1', parent='1',
                             style=f'rounded={int(bool(radius))};arcSize=10;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;dashed={int(dash)};')
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as':'geometry'})
        dashed = ' stroke-dasharray="7 6"' if dash else ''
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dashed}/>')

    def text(self, ident, label, x, y, w, h=28, size=20, color=INK, bold=False):
        assert 0 <= x and 0 <= y and x+w <= self.width and y+h <= self.height, (ident, x,y,w,h)
        self.texts.append((ident, label, x,y,w,h,size))
        cell = ET.SubElement(self.root, 'mxCell', id=ident, value=label, vertex='1', parent='1',
                             style=f'text;html=0;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;spacing=0;fontFamily=Arial;fontSize={size};fontColor={color};fontStyle={int(bold)};')
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as':'geometry'})
        self.svg.append(f'<text data-id="{ident}" x="{x}" y="{y+h/2}" dominant-baseline="central" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(label)}</text>')

    def card(self, ident, x, y, w, h, title, lines, tag=None, fill='white', stroke=BORDER, size=19):
        self.rect(ident,x,y,w,h,fill,stroke)
        ty = y+20
        if tag:
            self.text(ident+'-tag',tag,x+22,ty,w-44,22,15,BLUE,True)
            ty += 28
        self.text(ident+'-title',title,x+22,ty,w-44,32,25,INK,True)
        ty += 46
        for i, line in enumerate(lines):
            self.text(f'{ident}-line-{i}',line,x+22,ty,w-44,28,size,MUTED)
            ty += 32
        assert ty <= y+h+4, (ident, ty, y+h)

    def edge(self, ident, source, target, points, dashed=False):
        # Pin endpoints to explicit sides so draw.io and the SVG use the same routes.
        def port(ident,point):
            x,y,w,h=self.bounds[ident];px,py=point
            return (round((px-x)/w,6),round((py-y)/h,6))
        a,b=port(source,points[0]),port(target,points[-1])
        cell=ET.SubElement(self.root,'mxCell',id=ident,edge='1',parent='1',source=source,target=target,
                           style=f'edgeStyle=orthogonalEdgeStyle;rounded=0;strokeColor={BLUE};strokeWidth=2;endArrow=block;endFill=1;dashed={int(dashed)};exitX={a[0]};exitY={a[1]};exitDx=0;exitDy=0;entryX={b[0]};entryY={b[1]};entryDx=0;entryDy=0;')
        geo=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
        if len(points)>2:
            array=ET.SubElement(geo,'Array',attrib={'as':'points'})
            for x,y in points[1:-1]:ET.SubElement(array,'mxPoint',x=str(x),y=str(y))
        self.connections.append((ident,source,target,points))
        route=' '.join(f'{x},{y}' for x,y in points)
        dash=' stroke-dasharray="6 6"' if dashed else ''
        self.svg.append(f'<polyline points="{route}" fill="none" stroke="{BLUE}" stroke-width="2" marker-end="url(#arrow)"{dash}/>')

    def footer(self, lines):
        y=self.height-28-len(lines)*26
        for i,line in enumerate(lines):self.text(f'footer-{i}',line,50,y+i*26,self.width-100,25,17,MUTED)

    def save(self, chromium=None):
        OUT.mkdir(parents=True,exist_ok=True)
        ET.indent(self.mx)
        base=OUT/self.name
        base.with_suffix('.drawio').write_text(ET.tostring(self.mx,encoding='unicode')+'\n')
        base.with_suffix('.svg').write_text('\n'.join(self.svg+['</svg>'])+'\n')
        if chromium:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=chromium)
                page=browser.new_page(viewport={'width':self.width,'height':self.height},device_scale_factor=2)
                page.set_content('<html><body style="margin:0">'+base.with_suffix('.svg').read_text()+'</body></html>')
                overflow=page.locator('svg text').evaluate_all('els => els.map(e => ({id:e.dataset.id, width:e.getBBox().width} ))')
                limits={ident:w for ident,_,_,_,w,_,_ in self.texts}
                bad=[r for r in overflow if r['width']>limits[r['id']]+1]
                if bad:raise ValueError(f'Text exceeds assigned width: {bad}')
                page.screenshot(path=str(base.with_suffix('.png')))
                browser.close()
        return base.with_suffix('.svg')


def node(d, ident, x, y, title, detail='', w=340, fill='white'):
    d.card(ident,x,y,w,116,title,[detail] if detail else [],fill=fill,size=18)


def arrow(d, ident, source, target, points, label=None, label_at=None, dashed=False):
    d.edge(ident,source,target,points,dashed)
    if label:
        x,y,w=label_at
        d.text(ident+'-label',label,x,y,w,24,16,BLUE)


def overview():
    d=Diagram('semantic-hub-overview',1500,820,'From evidence to trusted answers',
              'A reviewed semantic release connects source data, business meaning, and cited evidence.')
    node(d,'data',60,210,'Source data','Tables and sample snapshots',400)
    node(d,'docs',60,410,'Documents','Text, scanned pages, and visual facts',400)
    node(d,'draft',550,310,'Build semantic context','Define metrics; link supporting evidence',400,'#EDF3FF')
    node(d,'review',1040,310,'Validate and review','Check SQL and approve definitions',400)
    arrow(d,'data-draft','data','draft',[(460,268),(505,268),(505,340),(550,340)])
    arrow(d,'docs-draft','docs','draft',[(460,468),(505,468),(505,396),(550,396)])
    arrow(d,'draft-review','draft','review',[(950,368),(1040,368)])
    node(d,'release',1040,600,'Publish a version','Freeze meaning, evidence, and source',400,'#EDF3FF')
    node(d,'playground',550,600,'Playground','Inspect interpretation → Run → answer',400)
    node(d,'agents',60,600,'External agents','MCP tools → sample results or citations',400)
    arrow(d,'review-release','review','release',[(1240,426),(1240,600)],'Publish',(1260,500,180))
    arrow(d,'release-playground','release','playground',[(1040,658),(950,658)])
    arrow(d,'release-agents','release','agents',[(1240,716),(1240,750),(260,750),(260,716)])
    d.footer(['One published release supplies both Playground and external agents.'])
    return d


def technical():
    d=Diagram('semantic-hub-technical-architecture',1600,1220,'Semantic Hub — technical architecture design',
              'Shared semantic context connects authoring and agents to governed queries across different data sources.')
    d.root.find("mxCell[@id='brand']").set('value','SEMANTIC HUB  /  TARGET ARCHITECTURE')
    d.svg=[part.replace('SEMANTIC HUB  /  IMPLEMENTED ARCHITECTURE','SEMANTIC HUB  /  TARGET ARCHITECTURE') for part in d.svg]
    xs=[70,630,1190]; w=340
    for label,y in [('CLIENTS',175),('SERVICES',425),('STORAGE',805)]:
        d.text('layer-'+str(y),label,70,y,1460,25,16,BLUE,True)
    node(d,'browser',70,220,'Studio browser','Model and document authoring')
    node(d,'pg-client',630,220,'Playground browser','Question and explicit Run')
    node(d,'mcp',1190,220,'External agent + MCP','stdio adapter → HTTPS API')
    d.rect('backend',45,465,1510,310,fill='#EDF3FF',stroke='#9FB9EF',dash=True)
    node(d,'author',70,490,'Authoring service','Extract → draft → validate → publish')
    node(d,'harness',630,490,'Playground Harness','Tools → checked plan → Run')
    node(d,'consumer',1190,490,'Consumer API','Resolve → compile → execute')
    node(d,'release',70,650,'Published context','Version + context + source bindings',340,'#F0F8F3')
    node(d,'engine',1190,650,'Query execution layer','Source connectors + query adapters')
    for a,b,x in [('browser','author',240),('pg-client','harness',800),('mcp','consumer',1360)]:
        arrow(d,a+'-request',a,b,[(x,336),(x,490)])
    arrow(d,'publish','author','release',[(240,606),(240,650)])
    arrow(d,'context-harness','release','harness',[(410,680),(580,680),(580,548),(630,548)],'Read release',(440,620,145))
    arrow(d,'context-consumer','release','consumer',[(410,735),(1135,735),(1135,578),(1190,578)],'Pinned context',(750,739,210))
    arrow(d,'harness-engine','harness','engine',[(970,548),(1070,548),(1070,680),(1190,680)],'Run',(1080,625,80))
    arrow(d,'consumer-engine','consumer','engine',[(1360,606),(1360,650)])
    node(d,'state-db',70,850,'Relational database','Drafts, evidence, releases, and audit')
    node(d,'lance',630,850,'Lance vector caches','Optional embedding lookup')
    d.card('sources',1190,850,340,190,'Connected data sources',
           ['Databases','Warehouses and lakehouses','Files and object storage'],size=18)
    arrow(d,'release-store','release','state-db',[(240,766),(240,850)],'Persist',(260,790,90))
    arrow(d,'source-query','sources','engine',[(1360,850),(1360,766)],'Read data',(1380,790,120))
    arrow(d,'vectors-author','lance','author',[(700,850),(700,790),(20,790),(20,548),(70,548)],dashed=True)
    arrow(d,'vectors-consumer','lance','consumer',[(900,850),(900,790),(1580,790),(1580,548),(1530,548)],dashed=True)
    d.footer(['Target design: source-specific connectors and query adapters. Dashed arrows: optional vector lookup.',
              'Demo today: DuckDB over sample files; SQLite for state. Planned product state store: PostgreSQL.'])
    return d


def context_flow():
    d=Diagram('semantic-context-build-flow',1600,1220,'How semantic context is built',
              'Two input paths converge into one reviewed, versioned semantic release.')
    node(d,'schema',70,200,'Structured source','Schema + sample snapshot',420)
    node(d,'document',1090,200,'Uploaded document','Original file + revision + pages',420)
    node(d,'seed',70,390,'Seed model objects','Datasets, fields, and relationships',420)
    node(d,'extract',1090,390,'Extract and interpret','Text chunks / VLM visual observations',420)
    arrow(d,'schema-seed','schema','seed',[(280,316),(280,390)])
    arrow(d,'doc-extract','document','extract',[(1300,316),(1300,390)])
    node(d,'draft',590,390,'Draft semantic model','Metrics + joins + metadata',420,'#EDF3FF')
    arrow(d,'seed-draft','seed','draft',[(490,448),(590,448)])
    node(d,'evidence',1090,590,'Match and review evidence','Link passages to model objects',420)
    arrow(d,'extract-evidence','extract','evidence',[(1300,506),(1300,590)],'Keyword / optional vectors',(1100,535,370))
    arrow(d,'draft-targets','draft','evidence',[(1010,468),(1050,468),(1050,625),(1090,625)])
    arrow(d,'attach-evidence','evidence','draft',[(1090,670),(1030,670),(1030,490),(1010,490)])
    d.text('attach-label','Attach reviewed passages',1090,715,400,25,16,BLUE)
    node(d,'facts',70,590,'Review visual facts','Create source + draft from approved rows',420)
    arrow(d,'extract-facts','extract','facts',[(1300,390),(1300,350),(35,350),(35,648),(70,648)],'Optional document-derived source',(570,320,400),True)
    arrow(d,'facts-draft','facts','draft',[(490,648),(540,648),(540,480),(590,480)],dashed=True)
    node(d,'validate',590,740,'Validate the exact draft','Model checks + reference SQL',420)
    arrow(d,'draft-validate','draft','validate',[(800,506),(800,740)])
    node(d,'review',590,930,'Human review','Approve required objects and version',420)
    arrow(d,'validation-review','validate','review',[(800,856),(800,930)],'Passed validation',(820,880,240))
    node(d,'release',1090,930,'Publish frozen context','Definitions + evidence + source binding',420,'#F0F8F3')
    arrow(d,'review-publish','review','release',[(1010,988),(1090,988)])
    arrow(d,'rework','validate','draft',[(590,798),(555,798),(555,420),(590,420)],'Revise',(450,700,100),True)
    d.text('release-use','Pinned release → Playground / MCP',1090,1080,440,30,21,BLUE,True)
    d.footer(['AI proposes; people approve. Documents support definitions. Reviewed visual rows can also create a separate structured source.',
              'Release identity: model + version + context hash + source snapshot hash. Consumers use published context only.'])
    return d


def playground():
    d=Diagram('playground-agent-architecture',1500,820,'Playground — from question to checked answer',
              'The agent prepares an interpretation. The user authorizes execution with Run.')
    for ident,x,title,detail in [('question',60,'Question','Selected release + original scope'),('agent',560,'Harness agent','Inspect context and call bounded tools'),('plan',1060,'Checked plan','Server validation + query review')]:
        node(d,ident,x,230,title,detail,380)
    arrow(d,'ask','question','agent',[(440,288),(560,288)])
    arrow(d,'plan-result','agent','plan',[(940,288),(1060,288)])
    node(d,'context',560,460,'Published context','Definitions, passages, and source binding',380,'#EDF3FF')
    arrow(d,'context-agent','context','agent',[(750,460),(750,346)],'Read',(770,395,100))
    node(d,'run',1060,620,'User clicks Run','Revalidate release, scope, and plan',380)
    node(d,'execute',560,620,'Execute','DuckDB query or cited document QA',380)
    node(d,'answer',60,620,'Answer + provenance','Result, SQL or citations, and version',380,'#F0F8F3')
    arrow(d,'plan-run','plan','run',[(1250,346),(1250,620)],'Inspect interpretation',(1270,460,220))
    arrow(d,'run-execute','run','execute',[(1060,678),(940,678)])
    arrow(d,'execute-answer','execute','answer',[(560,678),(440,678)])
    d.footer(['Unsupported scope or missing data → clarification or limitation. No executable plan is issued.'])
    return d


BUILDERS={'overview':overview,'technical':technical,'context':context_flow,'playground':playground}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--diagram',choices=BUILDERS,default='overview')
    parser.add_argument('--chromium',help='Chromium executable for PNG exports and text-fit checks')
    args=parser.parse_args()
    for name in BUILDERS if args.all else [args.diagram]:
        print(BUILDERS[name]().save(args.chromium))


if __name__=='__main__':main()
