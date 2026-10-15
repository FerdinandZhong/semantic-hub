"""Launch the existing Helios console with one explicitly selected local sample pack."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "shared"))


def main() -> None:
    from helios_core.demo.registry import DemoError, PackRegistry
    from helios_core.demo.runtime import DemoRuntime, ExampleRequest, review_pack

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=os.environ.get("HELIOS_DEMO_DATASET"))
    parser.add_argument("--ui-mode", choices=["query"], default="query")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(os.environ.get("HELIOS_DEMO_REGISTRY", ROOT / "apps/helios/demo-packs.json")),
    )
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=Path(
            os.environ.get(
                "HELIOS_DEMO_FIXTURES", ROOT / "apps/helios-ds-generation/fixtures/sectors/v1"
            )
        ),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(os.environ.get("HELIOS_DEMO_STATE", ROOT / "state/demo")),
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--inspect", action="store_true", help="Print definitions for operator review"
    )
    actions.add_argument(
        "--review", action="store_true", help="Record explicit local sample review"
    )
    actions.add_argument(
        "--check", action="store_true", help="Execute reviewed predefined examples, then exit"
    )
    parser.add_argument("--reviewer")
    parser.add_argument("--release", help="Exact snapshot hash shown by --inspect")
    parser.add_argument(
        "--settings", type=Path, help="Optional saved pack_id and snapshot_sha256 binding"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--llm-token-file", type=Path, help="Read a proposal-provider credential into process memory")
    parser.add_argument("--llm-model", default="gpt-4o", help="Model used with --llm-token-file")
    parser.add_argument("--llm-base-url", default="https://api.openai.com/v1", help="OpenAI-compatible URL used with --llm-token-file")
    args = parser.parse_args()
    if not args.dataset:
        parser.error("Select --dataset or set HELIOS_DEMO_DATASET")
    try:
        registry = PackRegistry(args.registry, args.fixtures_root)
        pack = registry.load(args.dataset)
        if args.settings:
            saved = json.loads(args.settings.read_text())
            expected = {"pack_id": pack.entry.id, "snapshot_sha256": pack.fingerprint}
            if saved != expected:
                raise DemoError("Saved settings do not match the selected dataset and release")
        if args.release and args.release != pack.fingerprint:
            raise DemoError("Requested release does not match the selected snapshot")
        if args.inspect:
            print(
                json.dumps(
                    {
                        "pack_id": pack.entry.id,
                        "snapshot_sha256": pack.fingerprint,
                        "source": pack.source_name,
                        "generation_mode": pack.generation_mode,
                        "examples": [e.model_dump() for e in pack.entry.examples],
                        "model": pack.model_document(),
                    },
                    indent=2,
                )
            )
            return
        if args.review:
            if not args.reviewer or not args.release:
                parser.error("--review requires --reviewer and --release from --inspect")
            print(review_pack(pack, args.state_dir, args.reviewer))
            return
        if args.check:
            runtime = DemoRuntime(pack, args.state_dir)
            try:
                for example in pack.entry.examples:
                    result = runtime.execute(
                        ExampleRequest(
                            pack_id=pack.entry.id,
                            snapshot_sha256=pack.fingerprint,
                            session_id=runtime.session_id,
                            example_id=example.id,
                        )
                    )
                    print(json.dumps(result))
            finally:
                runtime.close()
            return
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Demo configuration rejected: {exc}\n")

    if args.llm_token_file:
        try:
            token = args.llm_token_file.expanduser().read_text().strip()
        except OSError:
            parser.exit(2, "Could not read the proposal-provider credential file.\n")
        if not token:
            parser.exit(2, "The proposal-provider credential file is empty.\n")
        os.environ.update(LLM_PROVIDER="openai", INFERENCE_BASE_URL=args.llm_base_url,
                          INFERENCE_MODEL=args.llm_model, INFERENCE_TOKEN=token)

    os.environ.update(
        {
            "HELIOS_DEMO_DATASET": args.dataset,
            "HELIOS_DEMO_REGISTRY": str(args.registry.resolve()),
            "HELIOS_DEMO_FIXTURES": str(args.fixtures_root.resolve()),
            "HELIOS_DEMO_STATE": str(args.state_dir.resolve()),
        }
    )
    # Demo launches keep console metadata away from the existing operator database.
    os.environ["HELIOS_METADATA_DB"] = str(args.state_dir.resolve() / "console.db")
    os.environ.setdefault("PYSTOW_HOME", str(args.state_dir.resolve() / "pystow"))
    import uvicorn

    uvicorn.run("apps.helios.console.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
