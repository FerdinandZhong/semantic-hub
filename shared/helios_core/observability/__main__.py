"""CLI: discover, optionally propose, publish reviewed drafts, inspect pinned releases."""
import argparse
import json
import os
import sys
from pathlib import Path

from . import DiscoveryError, Source, approve, discover, draft, load_release, propose, publish, search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('discover')
    scan.add_argument('--config', required=True)
    scan.add_argument('--output', required=True)
    scan.add_argument('--propose', action='store_true')
    release = commands.add_parser('publish')
    release.add_argument('--draft', required=True)
    release.add_argument('--directory', required=True)
    release.add_argument('--reviewer', required=True)
    release.add_argument('--version', required=True)
    release.add_argument('--confirm', action='store_true')
    lookup = commands.add_parser('search')
    lookup.add_argument('--release', required=True)
    lookup.add_argument('--sha256', required=True)
    lookup.add_argument('--question', required=True)
    args = parser.parse_args()
    if args.command == 'discover':
        sources = []
        for config in json.loads(Path(args.config).read_text())['sources']:
            values = dict(config)
            for field in ('username', 'password', 'token'):
                variable = values.pop(field + '_env', None)
                if variable:
                    if not os.environ.get(variable):
                        parser.error('A configured credential environment variable is missing')
                    values[field] = os.environ[variable]
                elif field in values:
                    parser.error('Use credential environment references, not inline credentials')
            sources.append(Source.model_validate(values))
        document = draft(discover(sources))
        if args.propose:
            from helios_core.llm import llm_from_env
            llm = llm_from_env()
            if llm is None:
                parser.error('Configure an inference endpoint before requesting proposals')
            document = propose(document, llm)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2)
        print(json.dumps({'status': 'draft', 'items': len(document['items'])}))
    elif args.command == 'publish':
        document = approve(json.loads(Path(args.draft).read_text()), reviewer=args.reviewer,
                           version=args.version, confirmed=args.confirm)
        path, checksum = publish(document, args.directory)
        print(json.dumps({'release': str(path), 'sha256': checksum}))
    else:
        print(json.dumps(search(load_release(args.release, args.sha256), args.question), indent=2))


if __name__ == '__main__':
    try:
        main()
    except DiscoveryError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, OSError, RuntimeError):
        print('Context operation failed; check configuration, review gates and file permissions.', file=sys.stderr)
        sys.exit(1)
