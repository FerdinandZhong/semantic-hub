"""One CAI ingress, one workspace, and one process for Studio and consumer API."""
from __future__ import annotations
from contextlib import asynccontextmanager
import os
import sys


def create_app(*, local=False):
    from cai_integration.config import configure_runtime
    cfg = configure_runtime()
    if not local and not all(os.environ.get(k) for k in ('CDSW_APP_PORT', 'CDSW_PROJECT_ID', 'CDSW_DOMAIN')):
        raise RuntimeError('CAI deployment requires an authenticated CAI Application. Use --local only for loopback testing.')
    sys.path.insert(0, str(cfg['root'] / 'shared'))
    from apps.helios.console.main import app as console
    from apps.helios.console.semantic_hub_api import create_application
    app = create_application(console.state.demo_hub, console.state.demo_llm_settings,
                             local_no_auth=local, platform_auth=not local)
    from semantic_hub.api import install
    install(app, console.state.demo_hub, cfg['state'], local=local)
    # Mounted applications do not run their lifespan automatically.
    @asynccontextmanager
    async def lifespan(application):
        async with console.router.lifespan_context(console):
            yield
    app.router.lifespan_context = lifespan
    @app.get('/healthz', include_in_schema=False)
    def health():
        return {'status': 'ready', 'service': 'Semantic Hub', 'authentication': 'local' if local else 'cai_ingress'}
    # Specific consumer and Swagger routes are registered before the UI catch-all.
    app.mount('/', console)
    return app


def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', action='store_true', help='Loopback-only smoke test without CAI ingress')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    port = args.port if args.local else int(os.environ.get('CDSW_APP_PORT', '0'))
    if not port or not 1 <= port <= 65535:
        parser.error('CAI must inject CDSW_APP_PORT; local tests require --local --port PORT.')
    uvicorn.run(create_app(local=args.local), host='127.0.0.1',
                port=port, workers=1, access_log=False)


if __name__ == '__main__':
    main()
