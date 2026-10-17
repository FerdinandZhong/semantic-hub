"""Generate matching, editable draw.io and slide-ready SVG architecture diagrams."""
from pathlib import Path
import argparse
import html
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/diagrams/semantic-hub-overview'
W, H = 1600, 900
BLACK = '#000000'


def build():
    mxfile = ET.Element('mxfile', host='app.diagrams.net', type='device')
    diagram = ET.SubElement(mxfile, 'diagram', id='semantic-hub-overview', name='Semantic Hub overview')
    model = ET.SubElement(diagram, 'mxGraphModel', dx=str(W), dy=str(H), grid='1', gridSize='10',
                          guides='1', tooltips='1', connect='1', arrows='1', fold='1',
                          page='1', pageScale='1', pageWidth=str(W), pageHeight=str(H), math='0', shadow='0')
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<title>Semantic Hub high-level architecture</title>',
           '<desc>Three horizontal semantic models connect to external data and documents. AI drafts definitions. Humans validate before versioned publication and consumption.</desc>',
           '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 Z" fill="#000000"/></marker></defs>',
           '<rect width="1600" height="900" fill="#ffffff"/>']
    rectangles = {}

    def cell(ident, value, style, x, y, width, height, parent='1'):
        item = ET.SubElement(root, 'mxCell', id=ident, value=value, style=style, vertex='1', parent=parent)
        ET.SubElement(item, 'mxGeometry', x=str(x), y=str(y), width=str(width), height=str(height), attrib={'as': 'geometry'})
        return item

    def text(ident, label, x, y, width, height=30, size=22, bold=False, align='center', parent='1', offset=(0, 0)):
        style = f'text;html=1;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;whiteSpace=wrap;rounded=0;fontFamily=Arial;fontSize={size};fontColor={BLACK};fontStyle={1 if bold else 0};'
        cell(ident, html.escape(label), style, x, y, width, height, parent)
        ax, ay = x + offset[0], y + offset[1]
        tx = ax + width / 2 if align == 'center' else ax
        anchor = 'middle' if align == 'center' else 'start'
        svg.append(f'<text x="{tx}" y="{ay + height / 2}" dominant-baseline="central" text-anchor="{anchor}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{BLACK}">{html.escape(label)}</text>')

    def box(ident, x, y, width, height, parent='1', offset=(0, 0), container=False):
        style = 'rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=2;shadow=0;'
        if container:
            style += 'container=1;collapsible=0;recursiveResize=0;'
        cell(ident, '', style, x, y, width, height, parent)
        ax, ay = x + offset[0], y + offset[1]
        rectangles[ident] = (ax, ay, width, height)
        svg.append(f'<rect x="{ax}" y="{ay}" width="{width}" height="{height}" fill="#ffffff" stroke="#000000" stroke-width="2"/>')

    def edge(ident, source, target, points, exit_x=.5, exit_y=1, entry_x=.5, entry_y=0):
        style = f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#000000;strokeWidth=2;endArrow=block;endFill=1;exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;'
        item = ET.SubElement(root, 'mxCell', id=ident, style=style, edge='1', parent='1', source=source, target=target)
        geo = ET.SubElement(item, 'mxGeometry', relative='1', attrib={'as': 'geometry'})
        if len(points) > 2:
            array = ET.SubElement(geo, 'Array', attrib={'as': 'points'})
            for px, py in points[1:-1]:
                ET.SubElement(array, 'mxPoint', x=str(px), y=str(py))
        coordinates = ' '.join(f'{px},{py}' for px, py in points)
        svg.append(f'<polyline points="{coordinates}" fill="none" stroke="#000000" stroke-width="2" marker-end="url(#arrow)"/>')

    text('title', 'Semantic Hub | From sources to governed semantic models', 60, 20, 1480, 44, 30, True, 'left')
    box('ai', 615, 88, 370, 76)
    text('ai-title', 'AI MODELS', 635, 96, 330, 28, 22, True)
    text('ai-description', 'Interpret sources · Draft definitions', 625, 127, 350, 24, 18)

    hub_x, hub_y = 140, 205
    box('hub', hub_x, hub_y, 1320, 280, container=True)
    text('hub-title', 'SEMANTIC HUB', 25, 14, 1270, 36, 28, True, parent='hub', offset=(hub_x, hub_y))
    text('shared', 'Definitions · Metrics · Relationships · Ontology · Metadata · Evidence lineage',
         25, 58, 1270, 28, 20, parent='hub', offset=(hub_x, hub_y))

    entries = [
        ('finance', 30, 'Finance model', 'Payment roles and relationships', 'Metric: settled outflow in SGD',
         'FINANCE SOURCES', 'Payments · Accounts · Transactions', 'Document: HSBC payment guide'),
        ('manufacturing', 460, 'Manufacturing model', 'Assets, readings, and work orders', 'Metric: recorded downtime',
         'MANUFACTURING SOURCES', 'Assets · Sensor readings', 'Work orders'),
        ('pharma', 890, 'Pharma intelligence model', 'Drugs, trials, and approvals', 'Metrics: approvals and sales share',
         'PHARMA SOURCES', 'Curated FDA and industry records', 'Documents: FDA / EFPIA PDFs'),
    ]
    for ident, x, title, line1, line2, source_title, source1, source2 in entries:
        ax = hub_x + x
        box(ident, x, 112, 400, 138, parent='hub', offset=(hub_x, hub_y))
        text(ident+'-title', title, x+10, 128, 380, 32, 24, True, parent='hub', offset=(hub_x, hub_y))
        text(ident+'-line1', line1, x+10, 176, 380, 25, 19, parent='hub', offset=(hub_x, hub_y))
        text(ident+'-line2', line2, x+10, 209, 380, 25, 19, parent='hub', offset=(hub_x, hub_y))
        box(ident+'-source', ax, 555, 400, 115)
        text(ident+'-source-title', source_title, ax+10, 567, 380, 27, 20, True)
        text(ident+'-source1', source1, ax+10, 605, 380, 24, 18)
        text(ident+'-source2', source2, ax+10, 636, 380, 24, 18)
        edge(ident+'-interpret', ident+'-source', ident, [(ax+200, 555), (ax+200, 455)], exit_y=0, entry_y=1)
        # Keep text beside the connector, not across its vertical line.
        text(ident+'-interpret-label', 'Interpret data', ax+213, 496, 180, 23, 16, align='left')
        if ident != 'manufacturing':
            text(ident+'-evidence-label', 'Link reviewed evidence', ax+213, 522, 180, 23, 15, align='left')

    edge('ai-draft', 'ai', 'hub', [(800, 164), (800, 205)])

    workflow = [
        ('review', 170, 'HUMAN REVIEW', 'Annotate and correct definitions', 'Validate SQL and document evidence'),
        ('publish', 600, 'VERSION & PUBLISH', 'Freeze reviewed models and evidence', 'Version history and comparison'),
        ('consume', 1030, 'APPLICATIONS & AGENTS', 'Playground: verify sample answers', 'API / MCP: external agent context'),
    ]
    for ident, x, title, line1, line2 in workflow:
        box(ident, x, 755, 400, 120)
        text(ident+'-title', title, x+10, 765, 380, 30, 22, True)
        text(ident+'-line1', line1, x+10, 809, 380, 24, 18)
        text(ident+'-line2', line2, x+10, 841, 380, 24, 18)
    text('workflow-label', 'Hub review and release workflow', 170, 710, 600, 28, 20, True, 'left')
    edge('draft-review', 'hub', 'review', [(140, 345), (90, 345), (90, 815), (170, 815)],
         exit_x=0, exit_y=.5, entry_x=0, entry_y=.5)
    edge('review-publish', 'review', 'publish', [(570, 815), (600, 815)], exit_x=1, exit_y=.5, entry_x=0, entry_y=.5)
    edge('publish-consume', 'publish', 'consume', [(1000, 815), (1030, 815)], exit_x=1, exit_y=.5, entry_x=0, entry_y=.5)
    svg.append('</svg>')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(mxfile)
    OUT.with_suffix('.drawio').write_text(ET.tostring(mxfile, encoding='unicode')+'\n')
    OUT.with_suffix('.svg').write_text('\n'.join(svg)+'\n')
    return OUT.with_suffix('.svg')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', help='Optional Chromium executable for a 3200×1800 PNG export')
    args = parser.parse_args()
    svg_path = build()
    if args.chromium:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium)
            page = browser.new_page(viewport={'width': W, 'height': H}, device_scale_factor=2)
            page.set_content('<html><body style="margin:0;background:white">'+svg_path.read_text()+'</body></html>')
            page.screenshot(path=str(OUT.with_suffix('.png')))
            browser.close()
    print('Created', OUT.with_suffix('.drawio'), 'and', svg_path)
