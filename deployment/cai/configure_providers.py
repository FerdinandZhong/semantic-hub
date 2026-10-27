"""Register only verified navigation capabilities using protected Hub state."""

import os
from semantic_hub.providers.registry import Registry


def configure(mode, *, state=None):
    if mode == "builtin_only":
        return None
    if mode == "bundled":
        apps = state["applications"]
        ui, api = apps["helios_ui"]["origin"], apps["helios_api"]["origin"]
    elif mode == "external":
        ui, api = os.environ.get("HELIOS_UI_ORIGIN", ""), os.environ.get(
            "HELIOS_API_ORIGIN", ""
        )
    else:
        raise ValueError("Unknown provider mode.")
    from deployment.launchers.common import configuration

    root = configuration()["hub"]
    return Registry(root, local=False).save_provider("helios", "Helios", ui, api)
