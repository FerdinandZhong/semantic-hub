"""Child bootstrap: import native modules only from the pinned checkout."""

import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
service, port = sys.argv[2], int(sys.argv[3])
sys.path[:0] = [str(root), str(root / "shared")]
if os.environ.get("HELIOS_DEV") or os.environ.get("HELIOS_DEV_USER"):
    raise RuntimeError("Development identity is forbidden")
if service == "hub":
    from cai_integration.application import create_app

    app = create_app(local=False)
elif service in {"helios-api", "helios-ui"}:
    import helios_core

    if not Path(helios_core.__file__).resolve().is_relative_to(root):
        raise RuntimeError("Native helios_core origin mismatch")
    if service == "helios-ui":
        from apps.helios.ui import app as native
    else:
        from apps.helios.console import main as native
    if not Path(native.__file__).resolve().is_relative_to(root):
        raise RuntimeError("Native application origin mismatch")
    if service == "helios-ui":
        native.main()
        raise SystemExit
    app = native.app
else:
    raise RuntimeError("Unknown service")
import uvicorn  # noqa: E402 - load only after isolated provider imports

uvicorn.run(app, host="127.0.0.1", port=port, access_log=False, proxy_headers=False)
