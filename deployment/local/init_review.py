"""Opt-in empty native workspace; never publish artifacts or fabricate query data.

Usage: .venv-helios/bin/python -I deployment/local/init_review.py [state/local-v2]
"""

import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
state = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "state/local-v2"
checkout = root / "external/helios"
sys.path[:0] = [str(checkout), str(checkout / "shared")]
os.environ["HELIOS_METADATA_DB"] = str(state / "helios/helios.db")
from helios_core import authz  # noqa: E402
from helios_core.domain import (  # noqa: E402
    Model,
    Organization,
    DataSource,
    DataSourceReference,
)  # noqa: E402
from helios_core.metadata import PrincipalRecord, SQLiteMetadataRepository  # noqa: E402

repo = SQLiteMetadataRepository()
repo.migrate()
organization = "local-review"
model = "empty-review"
principal = "cloudera-workbench:local-reviewer"
if (
    repo.model(model) is not None
    or repo.organization(organization) is not None
    or repo.data_source("local-unconfigured") is not None
):
    raise SystemExit("Review IDs already exist. Existing metadata was not changed.")
if repo.organization(organization) is None:
    repo.save_organization(
        Organization(organization, "Local review"), slug=organization
    )
if repo.principal(principal) is None:
    repo.save_principal(
        PrincipalRecord(
            id=principal,
            external_identity="local-reviewer",
            display_name="Local reviewer",
        )
    )
repo.add_organization_membership(organization, principal, authz.Role.ORG_ADMIN)
repo.save_data_source(
    DataSource(
        id="local-unconfigured",
        organization_id=organization,
        name="Unconfigured local connection",
        connector="impala",
        connection_ref="env:IMPALA_HOST",
    )
)
repo.save_model(
    Model(
        id=model,
        organization_id=organization,
        name="Empty review model",
        description="Local empty draft; no published artifacts or query data.",
        data_sources=(DataSourceReference("local-unconfigured"),),
    ),
    created_by=principal,
    status="draft",
)
print("Created authorized empty draft: organization=local-review model=empty-review")
