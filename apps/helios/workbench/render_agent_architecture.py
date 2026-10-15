"""Render the editable architecture SVG to PNG with an installed Chromium."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--chromium',help='Optional path to an existing Chromium executable')
    parser.add_argument('--diagram',type=Path,default=ROOT/'docs/diagrams/playground-agent-architecture.svg')
    args=parser.parse_args()
    diagram=args.diagram.resolve()
    svg=ET.parse(diagram).getroot()
    with sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':args.chromium} if args.chromium else {}))
        page=browser.new_page(viewport={'width':int(svg.attrib['width']),'height':int(svg.attrib['height'])},device_scale_factor=1)
        page.goto(diagram.as_uri())
        page.screenshot(path=str(diagram.with_suffix('.png')))
        browser.close()
    print(diagram.with_suffix('.png'))

if __name__=='__main__':main()
