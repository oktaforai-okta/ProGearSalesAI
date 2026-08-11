#!/usr/bin/env python3
"""Run the notebook's real Okta path with temporary, cleaned-up test objects.

The script expects an Okta API token in ``OKTA_API_TOKEN``. It adds a temporary
user, agent signing key, and localhost redirect URI, executes the notebook's
code cells, proves an allowed and denied scope, and restores the tenant.
Secrets and raw tokens are never printed.
"""

from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import os
import re
import secrets
import string
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "progear-inventory-authorization-story.ipynb"
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")


def b64url_int(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).rstrip(b"=").decode()


def private_jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, str]:
    private = key.private_numbers()
    public = private.public_numbers
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": b64url_int(public.n),
        "e": b64url_int(public.e),
        "d": b64url_int(private.d),
        "p": b64url_int(private.p),
        "q": b64url_int(private.q),
        "dp": b64url_int(private.dmp1),
        "dq": b64url_int(private.dmq1),
        "qi": b64url_int(private.iqmp),
    }


def public_jwk(jwk: dict[str, str]) -> dict[str, str]:
    return {name: jwk[name] for name in ("kid", "kty", "alg", "use", "e", "n")}


class Okta:
    def __init__(self, domain: str, token: str) -> None:
        self.domain = domain.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"SSWS {token}", "Accept": "application/json"}
        )

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{self.domain}{path}"
        response = self.session.request(method, url, timeout=20, **kwargs)
        if not response.ok:
            try:
                body = response.json()
                detail = body.get("errorSummary") or body.get("error") or "request denied"
            except ValueError:
                detail = "non-JSON response"
            raise RuntimeError(f"Okta {method} {urlparse(url).path} failed: HTTP {response.status_code} ({detail})")
        return response


def app_update_payload(app: dict) -> dict:
    fields = ("name", "label", "signOnMode", "credentials", "settings", "visibility", "features", "profile")
    return {field: copy.deepcopy(app[field]) for field in fields if field in app}


def create_test_user(okta: Okta, group_id: str, suffix: str) -> tuple[dict, str]:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    password = "N1!" + "".join(secrets.choice(alphabet) for _ in range(25))
    login = f"notebook.live.{suffix}@atko.email"
    profile = {
        "firstName": "Notebook",
        "lastName": "Live Test",
        "email": login,
        "login": login,
        "mobilePhone": "+15555550123",
    }
    schema = okta.request("GET", "/api/v1/meta/schemas/user/default").json()
    custom = schema.get("definitions", {}).get("custom", {}).get("properties", {})
    for name, value in {
        "is_on_vacation": False,
        "is_a_manager": False,
        "clearance_level": 0,
    }.items():
        if name in custom:
            profile[name] = value

    response = okta.request(
        "POST",
        "/api/v1/users?activate=true",
        json={
            "profile": profile,
            "credentials": {"password": {"value": password}},
        },
    )
    user = response.json()
    try:
        okta.request("PUT", f"/api/v1/groups/{group_id}/users/{user['id']}")
    except Exception:  # noqa: BLE001 - cleanup must run for any assignment failure
        try:
            okta.request("POST", f"/api/v1/users/{user['id']}/lifecycle/deactivate")
            okta.request("DELETE", f"/api/v1/users/{user['id']}")
        finally:
            raise
    return user, password


def add_agent_key(okta: Okta, agent_id: str, jwk: dict[str, str]) -> dict:
    body = public_jwk(jwk) | {"status": "ACTIVE"}
    return okta.request(
        "POST",
        f"/workload-principals/api/v1/ai-agents/{agent_id}/credentials/jwks",
        json=body,
    ).json()


def get_or_add_client_secret(okta: Okta, app_id: str) -> tuple[dict, bool]:
    existing = okta.request("GET", f"/api/v1/apps/{app_id}/credentials/secrets").json()
    active = [item for item in existing if item.get("status") == "ACTIVE" and item.get("client_secret")]
    if active:
        return active[0], False
    created = okta.request("POST", f"/api/v1/apps/{app_id}/credentials/secrets", json={}).json()
    return created, True


def authenticate(okta: Okta, login: str, password: str, authorize_url: str, redirect_uri: str) -> str:
    authn = requests.post(
        f"{okta.domain}/api/v1/authn",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={"username": login, "password": password},
        timeout=20,
    )
    if not authn.ok:
        raise RuntimeError(f"Test-user authentication failed: HTTP {authn.status_code}")
    authn_body = authn.json()
    if authn_body.get("status") != "SUCCESS" or not authn_body.get("sessionToken"):
        raise RuntimeError(f"Test-user authentication did not finish: {authn_body.get('status', 'unknown')}")

    parsed = urlparse(authorize_url)
    query = parse_qs(parsed.query)
    query["sessionToken"] = [authn_body["sessionToken"]]
    query["prompt"] = ["none"]
    current = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    browser = requests.Session()
    for _ in range(10):
        response = browser.get(current, allow_redirects=False, timeout=20)
        location = response.headers.get("Location")
        if not location:
            raise RuntimeError(f"Authorization did not redirect: HTTP {response.status_code}")
        target = urljoin(current, location)
        if target.startswith(redirect_uri):
            values = parse_qs(urlparse(target).query)
            if values.get("error"):
                raise RuntimeError(f"Authorization failed: {values['error'][0]}")
            return target
        current = target
    raise RuntimeError("Authorization exceeded the redirect limit")


def execute_notebook(
    notebook_path: Path,
    values: dict[str, str],
    redirect_factory,
) -> tuple[dict, str]:
    notebook = json.loads(notebook_path.read_text())
    namespace: dict = {"__name__": "__notebook_live_test__"}
    transcript: list[str] = []

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if source.lstrip().startswith("%pip"):
            continue
        if "# @title Name your first integration" in source:
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                exec(compile(source, str(notebook_path), "exec"), namespace)  # noqa: S102
            transcript.append(output.getvalue())
            namespace.update(values)
            continue
        if "# @title Record the Okta-generated IDs once" in source:
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                exec(compile(source, str(notebook_path), "exec"), namespace)  # noqa: S102
            transcript.append(output.getvalue())
            namespace.update(values)
            continue
        if "# @title Complete the live redirect" in source and namespace.get("LIVE"):
            redirect_url = redirect_factory(namespace["authorize_url"])
            source = source.replace('REDIRECT_URL = ""', f"REDIRECT_URL = {redirect_url!r}", 1)

        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            exec(compile(source, str(notebook_path), "exec"), namespace)  # noqa: S102
        cell_output = output.getvalue()
        if JWT_PATTERN.search(cell_output):
            raise RuntimeError("A notebook cell displayed a raw JWT")
        transcript.append(cell_output)

    return namespace, "".join(transcript)


def prove_denied_scope(namespace: dict, denied_scope: str) -> None:
    id_jag_response = requests.post(
        namespace["ORG_TOKEN_URL"],
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": namespace["build_client_assertion"](namespace["ORG_TOKEN_URL"]),
            "subject_token": namespace["ID_TOKEN"],
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "requested_token_type": "urn:ietf:params:oauth:token-type:id-jag",
            "scope": denied_scope,
            "audience": namespace["CUSTOM_ISSUER"],
        },
        timeout=20,
    )
    if not id_jag_response.ok:
        return

    denied_id_jag = id_jag_response.json()["access_token"]
    token_response = requests.post(
        namespace["CUSTOM_TOKEN_URL"],
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": namespace["build_client_assertion"](namespace["CUSTOM_TOKEN_URL"]),
            "assertion": denied_id_jag,
        },
        timeout=20,
    )
    if token_response.ok:
        raise RuntimeError(f"Denied scope {denied_scope} unexpectedly received a resource token")


def audit_events(okta: Okta, since: datetime, agent_id: str, user_id: str) -> list[tuple[str, str, str, str]]:
    response = okta.request(
        "GET",
        "/api/v1/logs",
        params={
            "since": since.isoformat().replace("+00:00", "Z"),
            "sortOrder": "DESCENDING",
            "limit": 200,
        },
    )
    matched = []
    for event in response.json():
        encoded = json.dumps(event, separators=(",", ":"))
        if agent_id not in encoded and user_id not in encoded:
            continue
        matched.append(
            (
                event.get("eventType", "unknown"),
                event.get("outcome", {}).get("result", "unknown"),
                event.get("outcome", {}).get("reason", "") or "",
                event.get("debugContext", {}).get("debugData", {}).get("requestedScopes", "") or "",
            )
        )
    return sorted(set(matched))


def cleanup(
    okta: Okta,
    app_id: str,
    original_app: dict,
    owned_client_secret: dict | None,
    key: dict | None,
    agent_id: str,
    user: dict | None,
) -> list[str]:
    errors = []
    for label, action in (
        ("redirect URI", lambda: okta.request("PUT", f"/api/v1/apps/{app_id}", json=app_update_payload(original_app))),
        (
            "client secret",
            lambda: (
                okta.request(
                    "POST",
                    f"/api/v1/apps/{app_id}/credentials/secrets/{owned_client_secret['id']}/lifecycle/deactivate",
                ),
                okta.request(
                    "DELETE",
                    f"/api/v1/apps/{app_id}/credentials/secrets/{owned_client_secret['id']}",
                ),
            ) if owned_client_secret else None,
        ),
        (
            "agent key",
            lambda: (
                okta.request(
                    "POST",
                    f"/workload-principals/api/v1/ai-agents/{agent_id}/credentials/jwks/{key['id']}/lifecycle/deactivate",
                ),
                okta.request(
                    "DELETE",
                    f"/workload-principals/api/v1/ai-agents/{agent_id}/credentials/jwks/{key['id']}",
                ),
            ) if key else None,
        ),
        (
            "test user",
            lambda: (
                okta.request("POST", f"/api/v1/users/{user['id']}/lifecycle/deactivate"),
                okta.request("DELETE", f"/api/v1/users/{user['id']}"),
            ) if user else None,
        ),
    ):
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - report every cleanup failure
            errors.append(f"{label}: {exc}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--authorization-server-id", required=True)
    parser.add_argument("--allowed-group-id", required=True)
    parser.add_argument("--allowed-scope", required=True)
    parser.add_argument("--denied-scope", required=True)
    parser.add_argument("--redirect-uri", default="http://127.0.0.1:8765/authorization-code/callback")
    parser.add_argument(
        "--confirm-tenant-mutations",
        action="store_true",
        required=True,
        help="Acknowledge temporary user, key, and redirect-URI changes in a test tenant.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("OKTA_API_TOKEN")
    if not token:
        raise RuntimeError("OKTA_API_TOKEN is required")

    okta = Okta(args.domain, token)
    started = datetime.now(timezone.utc)
    suffix = secrets.token_hex(4)
    original_app = okta.request("GET", f"/api/v1/apps/{args.app_id}").json()
    agent = okta.request("GET", f"/workload-principals/api/v1/ai-agents/{args.agent_id}").json()
    auth_server = okta.request("GET", f"/api/v1/authorizationServers/{args.authorization_server_id}").json()
    test_user = None
    test_key = None
    test_client_secret = None
    owns_client_secret = False
    cleanup_errors: list[str] = []

    try:
        updated_app = app_update_payload(original_app)
        redirects = updated_app["settings"]["oauthClient"].setdefault("redirect_uris", [])
        if args.redirect_uri not in redirects:
            redirects.append(args.redirect_uri)
        okta.request("PUT", f"/api/v1/apps/{args.app_id}", json=updated_app)

        test_user, password = create_test_user(okta, args.allowed_group_id, suffix)
        key_material = private_jwk(
            rsa.generate_private_key(public_exponent=65537, key_size=2048),
            f"notebook-live-{suffix}",
        )
        test_key = add_agent_key(okta, args.agent_id, key_material)
        test_client_secret, owns_client_secret = get_or_add_client_secret(okta, args.app_id)

        os.environ["AGENT_PRIVATE_JWK"] = json.dumps(key_material, separators=(",", ":"))
        os.environ["USER_CLIENT_SECRET"] = test_client_secret["client_secret"]

        notebook_values = {
            "OKTA_DOMAIN": okta.domain,
            "AGENT_NAME": agent["profile"]["name"],
            "RESOURCE_NAME": auth_server["name"],
            "RESOURCE_URL": "",
            "RESOURCE_AUDIENCE": auth_server["audiences"][0],
            "RESOURCE_SCOPE": args.allowed_scope,
            "REDIRECT_URI": args.redirect_uri,
            "MODE": "Live Okta",
            "SIGN_IN_CLIENT_ID_INPUT": args.app_id,
            "AUTHORIZATION_SERVER_ID_INPUT": args.authorization_server_id,
            "AGENT_CLIENT_ID_INPUT": args.agent_id,
            "AGENT_KEY_ID_INPUT": key_material["kid"],
            "PREVIEW_USER_EMAIL": test_user["profile"]["login"],
            "PREVIEW_POLICY": "Allow requested scope",
        }

        namespace, transcript = execute_notebook(
            NOTEBOOK,
            notebook_values,
            lambda authorize_url: authenticate(
                okta,
                test_user["profile"]["login"],
                password,
                authorize_url,
                args.redirect_uri,
            ),
        )
        if not namespace.get("RESOURCE_TOKEN"):
            raise RuntimeError("The allowed notebook path did not issue a resource token")
        if args.allowed_scope not in namespace["granted_scopes"]:
            raise RuntimeError("The resource token did not contain the allowed scope")
        if namespace["resource_claims"].get("aud") != auth_server["audiences"][0]:
            raise RuntimeError("The resource token audience did not match the authorization server")
        if JWT_PATTERN.search(transcript):
            raise RuntimeError("The notebook transcript exposed a raw JWT")

        prove_denied_scope(namespace, args.denied_scope)
        events = []
        required_audit = {
            ("app.oauth2.token.grant.id_jag", args.allowed_scope),
            ("app.oauth2.as.token.grant.access_token", args.allowed_scope),
            ("app.oauth2.as.token.grant", args.denied_scope),
        }
        for _ in range(7):
            events = audit_events(okta, started, args.agent_id, test_user["id"])
            observed_audit = {(event[0], event[3]) for event in events}
            if required_audit.issubset(observed_audit):
                break
            time.sleep(3)
        observed_audit = {(event[0], event[3]) for event in events}
        missing_audit = required_audit - observed_audit
        if missing_audit:
            missing = ", ".join(f"{event_type} ({scope})" for event_type, scope in sorted(missing_audit))
            raise RuntimeError("System Log evidence was not indexed: " + missing)
        print("LIVE_NOTEBOOK_ALLOWED=PASS")
        print("LIVE_NOTEBOOK_DENIED=PASS")
        print("RAW_TOKEN_OUTPUT=PASS")
        print(f"AUDIT_EVENT_TYPES={len(events)}")
        for event_type, outcome, reason, requested_scopes in events:
            suffix = " ".join(value for value in (reason, requested_scopes) if value)
            print(f"AUDIT {outcome} {event_type}{' ' + suffix if suffix else ''}")
    finally:
        os.environ.pop("AGENT_PRIVATE_JWK", None)
        os.environ.pop("USER_CLIENT_SECRET", None)
        cleanup_errors = cleanup(
            okta,
            args.app_id,
            original_app,
            test_client_secret if owns_client_secret else None,
            test_key,
            args.agent_id,
            test_user,
        )

    if cleanup_errors:
        for error in cleanup_errors:
            print(f"CLEANUP_ERROR {error}", file=sys.stderr)
        return 1
    print("TENANT_CLEANUP=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
