"""Create a reviewed synthetic finance fixture in a NEW browser-test state directory."""

import argparse
from pathlib import Path

from apps.helios.tests.test_pharma_intelligence import registry
from apps.helios.tests.test_demo_context import validated, review_request, publish
from helios_core.demo.runtime import DemoRuntime

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
if args.state.exists() and any(args.state.iterdir()):
    raise SystemExit("Refusing to seed existing state. Use a new test directory.")
runtime = DemoRuntime(registry().load("finance"), args.state)
value = runtime.workspace.seed()
value["metrics"][0][
    "reference_sql"
] = "SELECT SUM(amount_sgd) AS total_amount_sgd FROM transactions WHERE status = 'SETTLED'"
validated(runtime, value)
runtime.workspace.review(review_request(runtime))
publish(runtime)
print(f"Reviewed synthetic test fixture created: {args.state.resolve()}")
