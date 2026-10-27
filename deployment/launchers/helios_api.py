"""CAI kernel-preserving helios-api launcher."""

import os
from pathlib import Path
import sys

root = Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()).resolve()
sys.path.insert(0, str(root))
from deployment.launchers.common import launch  # noqa: E402 - bootstrap project imports

if __name__ == "__main__":
    launch("helios-api")
