"""Isolated child entrypoint. The launcher invokes this file with Python -I."""

import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
service = sys.argv[2]
port = int(sys.argv[3])
if service == "hub":
    sys.path[:0] = [str(root), str(root / "shared")]
    from cai_integration.application import create_app

    app = create_app(local=True)
elif service == "helios-api":
    sys.path[:0] = [str(root), str(root / "shared")]
    from apps.helios.console.main import app
    import apps.helios.console.main as native
    import helios_core

    assert Path(native.__file__).resolve().is_relative_to(root)
    assert Path(helios_core.__file__).resolve().is_relative_to(root)
elif service == "helios-ui":
    sys.path[:0] = [str(root), str(root / "shared")]
    from apps.helios.ui.app import main

    main()
    raise SystemExit
else:
    raise SystemExit("Unknown service")
import uvicorn  # noqa: E402 - paths must be isolated before imports

uvicorn.run(app, host="127.0.0.1", port=port, access_log=False)
