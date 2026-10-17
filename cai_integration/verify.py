"""Offline installation check: immutable fixtures, imports, and required packages."""
import importlib
from pathlib import Path
import sys


def main():
    root = Path(globals().get('__file__', Path.cwd() / 'cai_integration/verify.py')).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / 'shared')]
    for name in ('fastapi', 'uvicorn', 'duckdb', 'sqlglot', 'cryptography', 'pypdf',
                 'docx', 'PIL', 'pypdfium2', 'lancedb', 'deepseek_harness', 'apps.helios.console.semantic_hub_api'):
        importlib.import_module(name)
    from helios_core.demo.registry import PackRegistry
    registry = PackRegistry(root / 'apps/helios/demo-packs.json', root / 'apps/helios-ds-generation/fixtures/sectors/v1')
    for key in registry.entries:
        registry.load(key)
        print('Verified source:', key)
    print('Runtime imports and fixture checksums passed.')


if __name__ == '__main__':
    main()
