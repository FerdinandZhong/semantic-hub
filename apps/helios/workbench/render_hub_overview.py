"""Refresh the editable Hub overview and optional PNG preview.

The shared architecture_diagrams.py generator also produces the technical and
Playground views. This entrypoint preserves the existing overview command.
"""
import argparse
from architecture_diagrams import OUT as DIAGRAM_DIR, overview

OUT = DIAGRAM_DIR / 'semantic-hub-overview'
W, H = 1500, 820


def build():
    return overview().save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', help='Optional Chromium executable for PNG export')
    args = parser.parse_args()
    print(overview().save(args.chromium))
