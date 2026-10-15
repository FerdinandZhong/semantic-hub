"""Launch all four real console demos; verify desktop/mobile results and isolation.

Requires the demo requirements, Playwright, and its Chromium browser.
Review receipts created here are test-only and removed with the temporary directory.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))


def main():
    from playwright.sync_api import expect, sync_playwright
    from helios_core.demo.registry import PackRegistry
    from helios_core.demo.runtime import review_pack

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/helios-demo-browser"))
    parser.add_argument("--pack", choices=["finance", "manufacturing", "pharma", "power"],
                        help="Check one pack when verifying a focused follow-up change")
    parser.add_argument(
        "--context-builder",
        action="store_true",
        help="Also verify the complete context authoring workflow",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT / "apps/helios-ds-generation/fixtures/sectors/v1"
    registry = PackRegistry(ROOT / "apps/helios/demo-packs.json", fixtures)
    outcomes = []
    with (
        tempfile.TemporaryDirectory(prefix="helios-demo-browser-") as temp,
        sync_playwright() as playwright,
    ):
        browser = playwright.chromium.launch(headless=True)
        try:
            for sector in registry.entries:
                if args.pack and sector != args.pack:
                    continue
                state = Path(temp) / sector
                pack = registry.load(sector)
                review_pack(pack, state, "automated-browser-test-only")
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                base = f"http://127.0.0.1:{port}"
                log_path = args.output / f"{sector}.log"
                with log_path.open("w") as log:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            str(ROOT / "start_demo.py"),
                            "--dataset",
                            sector,
                            "--state-dir",
                            str(state),
                            "--port",
                            str(port),
                        ],
                        cwd=ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env={**os.environ, "PYSTOW_HOME": str(state / "pystow")},
                    )
                    try:
                        deadline = time.monotonic() + 45
                        while True:
                            if process.poll() is not None:
                                raise RuntimeError(f"Console exited; inspect {log_path}")
                            try:
                                with urllib.request.urlopen(
                                    base + "/demo/api/config", timeout=1
                                ) as response:
                                    summary = json.load(response)
                                break
                            except (OSError, urllib.error.URLError):
                                if time.monotonic() > deadline:
                                    raise RuntimeError(
                                        f"Console startup timed out; inspect {log_path}"
                                    )
                                time.sleep(0.2)
                        assert summary["pack_id"] == sector
                        reference = json.loads(
                            (fixtures / sector / "evaluation/reference.json").read_text()
                        )
                        for width, height in [(1440, 1000), (390, 844)]:
                            page = browser.new_page(viewport={"width": width, "height": height})
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            page.goto(base + "/demo/query", wait_until="networkidle")
                            page.locator("#legacy-query").evaluate("el => el.open = true")
                            expect(page.locator("#run")).to_be_enabled()
                            expect(page.locator("#title")).to_have_text(pack.entry.title)
                            page.locator("#run").click()
                            expect(page.locator("#result")).to_be_visible(timeout=30000)
                            value = Decimal(page.locator("#value").inner_text().replace(",", ""))
                            assert abs(value - Decimal(reference["expected"])) < Decimal("1e-8")
                            assert page.evaluate(
                                "document.documentElement.scrollWidth <= window.innerWidth"
                            )
                            assert page.request.get(base + "/api/v1/assistant").status == 404
                            stale = page.request.post(
                                base + "/demo/api/example",
                                data={
                                    "pack_id": "other",
                                    "snapshot_sha256": pack.fingerprint,
                                    "session_id": summary["session_id"],
                                    "example_id": "aggregate",
                                },
                            )
                            assert stale.status == 409
                            assert not errors, errors
                            page.screenshot(
                                path=str(args.output / f"{sector}-{width}.png"), full_page=True
                            )
                            if args.context_builder:
                                from check_context_browser import check_context_builder

                                check_context_builder(
                                    page, base, pack, reference, width, args.output
                                )
                            assert not errors, errors
                            page.close()
                            outcomes.append(
                                {
                                    "pack": sector,
                                    "width": width,
                                    "value": str(value),
                                    "status": "passed",
                                }
                            )
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
        finally:
            browser.close()
    (args.output / "results.json").write_text(json.dumps(outcomes, indent=2) + "\n")
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
