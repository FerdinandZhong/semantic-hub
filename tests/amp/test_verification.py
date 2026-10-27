import io
from urllib.error import HTTPError

from deployment.cai.verify import probe, verify


def test_readiness_does_not_claim_identity_or_query_acceptance():
    calls = []

    def ready(origin, path, key):
        calls.append((origin, path))
        return {"reachable": True}

    report = verify(
        "bundled",
        "https://hub.example",
        {"helios_api": "https://api.example", "helios_ui": "https://ui.example"},
        probe_fn=ready,
    )
    assert len(calls) == 3 and report["endpoints_reachable"]
    assert report["cai_acceptance"] == "pending"
    assert not report["browser_identity_verified"]
    assert not report["native_query_verified"]


def test_builtin_verification_never_probes_provider():
    calls = []

    def failed(origin, path, key):
        calls.append(origin)
        return {"reachable": False}

    report = verify("builtin_only", "https://hub.example", probe_fn=failed)
    assert calls == ["https://hub.example"]
    assert not report["endpoints_reachable"]


def test_login_html_is_not_health():
    class Login:
        def open(self, request, timeout):
            response = io.BytesIO(b"<html>Login</html>")
            response.status = 200
            return response

    assert not probe("https://hub.example", "/healthz", opener=Login())["reachable"]


def test_redirect_is_reported_without_response_or_secret():
    class Redirect:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, 302, "sensitive error", {}, None)

    result = probe("https://hub.example", "/healthz", "private-key", opener=Redirect())
    assert result["http_status"] == 302
    assert "private-key" not in str(result) and "sensitive" not in str(result)
