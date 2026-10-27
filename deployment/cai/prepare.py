"""AMP setup: preserve Hub setup and prepare a separate locked native runtime."""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()).resolve()
sys.path.insert(0, str(ROOT))


def initialize_checkout(root):
    from deployment.local.run import validate_lock

    lock = json.loads((root / "deployment/provider-lock.json").read_text())["helios"]
    checkout = root / lock["path"]
    if not checkout.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Provider checkout must be inside the project")
    if not (checkout / ".git").exists():
        entry = (
            subprocess.check_output(
                ["git", "ls-tree", "HEAD", "--", lock["path"]], cwd=root, text=True
            )
            .strip()
            .split()
        )
        if len(entry) < 4 or entry[:3] != ["160000", "commit", lock["commit"]]:
            raise RuntimeError(
                "Provider Git submodule revision does not match the deployment lock"
            )
        subprocess.run(
            ["git", "submodule", "update", "--init", "--", lock["path"]],
            cwd=root,
            check=True,
        )
    return validate_lock(root)


def native_preflight():
    if os.environ.get("HELIOS_CAI_PROXY_AUTH_CONFIRMED") != "1":
        raise RuntimeError(
            "Bundled mode requires verified ingress and HELIOS_CAI_PROXY_AUTH_CONFIRMED=1"
        )
    if not os.environ.get("SEMANTIC_HUB_RUNTIME_IDENTIFIER"):
        raise RuntimeError("Bundled mode requires SEMANTIC_HUB_RUNTIME_IDENTIFIER")
    version = subprocess.check_output(["node", "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 20:
        raise RuntimeError("Native UI requires Node.js 20 or newer")
    return version


def prepare(root=ROOT):
    from deployment.launchers.common import configuration
    from deployment.local.run import validate_lock
    from cai_integration.environment import prepare_environment, check_isolation

    cfg = configuration(root)
    if cfg["mode"] == "bundled":
        version = native_preflight()
        checkout = initialize_checkout(root)
    elif cfg["mode"] == "external":
        from deployment.cai.provision import checked_origin

        checked_origin(os.environ.get("HELIOS_UI_ORIGIN", ""))
        checked_origin(os.environ.get("HELIOS_API_ORIGIN", ""))
    # Reuse the supported Hub setup, including its isolation and source checks.
    subprocess.run(
        [sys.executable, str(root / "cai_integration/setup_environment.py")],
        cwd=root,
        check=True,
    )
    cfg["deployment"].mkdir(parents=True, exist_ok=True)
    if cfg["mode"] != "bundled":
        return {"mode": cfg["mode"], "native_prepared": False}
    lock = json.loads((root / "deployment/provider-lock.json").read_text())["helios"]
    target = root / ".venv-helios"
    env = prepare_environment(target)
    requirements = []
    overrides = lock["local_dependency_overrides"]
    omitted = lock["optional_dependencies_omitted"]
    for line in (
        (checkout / "apps/helios/console/requirements.txt").read_text().splitlines()
    ):
        stripped = line.strip()
        package = stripped.split("==")[0]
        if (
            stripped
            and not stripped.startswith("#")
            and package not in omitted
            and package not in overrides
        ):
            requirements.append(stripped)
    requirements.extend(f"{key}=={value}" for key, value in overrides.items())
    reqfile = cfg["deployment"] / "helios-runtime-requirements.txt"
    reqfile.write_text("\n".join(requirements) + "\n")
    python = target / "bin/python"
    subprocess.run(
        [str(python), "-I", "-m", "pip", "install", "-r", str(reqfile)],
        env=env,
        cwd=checkout,
        check=True,
    )
    subprocess.run(
        [str(python), "-I", "-m", "pip", "check"], env=env, cwd=checkout, check=True
    )
    if not check_isolation(target, env):
        raise RuntimeError("Native runtime isolation failed")
    probe = (
        "import importlib.util,pathlib,sys;root=pathlib.Path(sys.argv[1]).resolve();"
        "sys.path[:0]=[str(root),str(root/'shared')];"
        "names=['helios_core','apps.helios.console.main','apps.helios.ui.app'];"
        "assert all(pathlib.Path(importlib.util.find_spec(name).origin).resolve().is_relative_to(root) for name in names)"
    )
    subprocess.run(
        [str(python), "-I", "-c", probe, str(checkout)],
        env=env,
        cwd=checkout,
        check=True,
    )
    # npm prebuild generates files. Build a disposable copy to preserve tracked checkout files.
    work = cfg["deployment"] / "helios-build" / lock["commit"]
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(
        checkout,
        work,
        ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "dist"),
    )
    ui = work / "apps/helios/ui"
    subprocess.run(["npm", "ci"], cwd=ui, env=env, check=True)
    dist = cfg["artifacts"] / "apps/helios/ui/dist"
    dist.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npm", "run", "build", "--", "--outDir", str(dist)],
        cwd=ui,
        env=env,
        check=True,
    )
    if not (dist / "index.html").is_file():
        raise RuntimeError("Native UI build is missing index.html")
    validate_lock(root)
    cfg["provider"].mkdir(parents=True, exist_ok=True)
    report = dict(
        mode=cfg["mode"],
        native_prepared=True,
        commit=lock["commit"],
        node=version,
        frontend_lock_sha256=hashlib.sha256(
            (ui / "package-lock.json").read_bytes()
        ).hexdigest(),
        requirements_sha256=hashlib.sha256(reqfile.read_bytes()).hexdigest(),
        limitations=lock["limitations"],
        identity_verified=False,
    )
    (cfg["deployment"] / "preparation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return report


if __name__ == "__main__":
    prepare()
