"""Additive provider/project records; never write native builder state."""

from __future__ import annotations
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit, urlencode


def origin(value: str, *, local: bool = False) -> str:
    value = value.strip().rstrip("/")
    p = urlsplit(value)
    loopback = p.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        p.scheme not in ({"https", "http"} if local and loopback else {"https"})
        or not p.hostname
        or p.username
        or p.password
        or p.path
        or p.query
        or p.fragment
    ):
        raise ValueError(
            "Use an HTTPS application origin without credentials, path, query, or fragment."
        )
    try:
        p.port
    except ValueError:
        raise ValueError("Invalid application port.") from None
    return value


class Registry:
    def __init__(self, root: Path, *, local=False):
        root.mkdir(parents=True, exist_ok=True)
        self.path, self.local = root / "providers.sqlite", local
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def providers(self):
        with self.connect() as db:
            records = [
                json.loads(row[0])
                for row in db.execute("SELECT body FROM providers ORDER BY id")
            ]
        return [
            dict(
                id="builtin",
                name="Built-in builder",
                kind="builtin",
                capabilities=["build", "query"],
                status="available",
            )
        ] + records

    def provider(self, ident):
        item = next((p for p in self.providers() if p["id"] == ident), None)
        if not item:
            raise ValueError("Provider not found.")
        return item

    def save_provider(self, ident, name, ui_origin, api_origin):
        if ident == "builtin" or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", ident):
            raise ValueError(
                "Use a unique provider ID with lowercase letters, numbers, and hyphens."
            )
        if not name.strip() or len(name) > 120:
            raise ValueError("A provider name of at most 120 characters is required.")
        item = dict(
            id=ident,
            name=name.strip(),
            kind="helios",
            ui_origin=origin(ui_origin, local=self.local),
            api_origin=origin(api_origin, local=self.local),
            capabilities=["launch_builder", "launch_query"],
            status="links_only",
        )
        with self.connect() as db:
            previous = db.execute(
                "SELECT body FROM providers WHERE id=?", (ident,)
            ).fetchone()
            if previous and json.loads(previous[0]) != item:
                raise ValueError(
                    "Provider already exists. Register a new ID to change its origins."
                )
            db.execute(
                "INSERT OR IGNORE INTO providers VALUES (?,?)",
                (ident, json.dumps(item)),
            )
        return item

    def projects(self):
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute("SELECT body FROM projects ORDER BY id")
            ]

    def add_project(self, name, provider_id, organization, model):
        import uuid

        p = self.provider(provider_id)
        if p["kind"] != "helios":
            raise ValueError(
                "Use the built-in source setup to create a local workspace."
            )
        if any(
            not isinstance(s, str) or not s.strip() or len(s) > 160
            for s in [name, organization, model]
        ):
            raise ValueError(
                "Name, organization, and model are required (maximum 160 characters each)."
            )
        item = dict(
            id="external-" + uuid.uuid4().hex,
            name=name.strip(),
            provider_id=provider_id,
            organization_id=organization.strip(),
            model_id=model.strip(),
        )
        with self.connect() as db:
            db.execute(
                "INSERT INTO projects VALUES (?,?)", (item["id"], json.dumps(item))
            )
        return item

    def links(self, project):
        p = self.provider(project["provider_id"])
        params = urlencode(
            {"organization": project["organization_id"], "model": project["model_id"]}
        )
        return {
            key: p["ui_origin"] + path + "?" + params
            for key, path in [
                ("studio", "/canvas"),
                ("sources", "/data-sources"),
                ("chat", "/talk"),
            ]
        }
