"""Bounded, caller-authorized access to a registered Helios API."""

import json
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException

MAX_BYTES = 2 * 1024 * 1024


class Discovery:
    def __init__(self, provider, key, *, local=False):
        if provider.get("kind") != "helios":
            raise HTTPException(422, "Select a registered Helios provider.")
        self.origin = provider["api_origin"]
        loopback = urlsplit(self.origin).hostname in {"localhost", "127.0.0.1", "::1"}
        if not key and not (local and loopback):
            raise HTTPException(401, "A Helios API key is required.")
        if key and (len(key) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in key)):
            raise HTTPException(422, "Invalid Helios API key.")
        self.headers = {"Accept": "application/json"}
        if key:
            self.headers["Authorization"] = "Bearer " + key

    def get(self, path, *, params=None):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(8.0), follow_redirects=False, trust_env=False
            ) as client:
                with client.stream(
                    "GET",
                    self.origin + "/api/v1" + path,
                    headers=self.headers,
                    params=params,
                ) as response:
                    if response.status_code in (401, 403, 404):
                        raise HTTPException(
                            response.status_code,
                            "Helios access denied or resource unavailable.",
                        )
                    if response.status_code != 200:
                        raise HTTPException(502, "Helios discovery failed.")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise HTTPException(
                                502, "Helios response exceeded the size limit."
                            )
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise HTTPException(
                502, "Helios returned an unavailable or invalid response."
            ) from None

    @staticmethod
    def record(value, *, model=False):
        fields = ("id", "name", "organization_id") if model else ("id", "name")
        if not isinstance(value, dict) or any(
            not isinstance(value.get(f), str)
            or not value[f].strip()
            or len(value[f]) > (1000 if f == "name" else 160)
            for f in fields
        ):
            raise HTTPException(502, "Helios returned invalid resource metadata.")
        return {f: value[f] for f in fields}

    def discover(self, organization_id=None):
        payload = self.get("/organizations")
        values = payload.get("organizations")
        if not isinstance(values, list):
            raise HTTPException(502, "Helios returned invalid organization metadata.")
        organizations = [self.record(v) for v in values]
        models = []
        if organization_id is not None:
            if organization_id not in {v["id"] for v in organizations}:
                raise HTTPException(403, "The selected organization is unavailable.")
            payload = self.get("/models", params={"organization_id": organization_id})
            if not isinstance(payload.get("models"), list):
                raise HTTPException(502, "Helios returned invalid model metadata.")
            models = [self.record(v, model=True) for v in payload["models"]]
            if any(v["organization_id"] != organization_id for v in models):
                raise HTTPException(502, "Helios returned inconsistent model metadata.")
        return {"organizations": organizations, "models": models}

    def verify(self, organization_id, model_id):
        model = self.record(self.get("/models/" + quote(model_id, safe="")), model=True)
        if model["id"] != model_id or model["organization_id"] != organization_id:
            raise HTTPException(
                403, "The selected model does not match the organization."
            )
        return model
