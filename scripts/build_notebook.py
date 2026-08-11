#!/usr/bin/env python3
"""Build the newcomer-friendly ProGear Cross-App Access Colab notebook."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "progear-inventory-authorization-story.ipynb"


def _source(value: str) -> list[str]:
    return dedent(value).strip("\n").splitlines(keepends=True)


def markdown(value: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": _source(value),
    }


def code(value: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _source(value),
    }


cells = [
    markdown(
        r'''
        <a href="https://colab.research.google.com/github/oktaforai-okta/ProGearSalesAI/blob/main/notebooks/progear-inventory-authorization-story.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>
        '''
    ),
    markdown(
        r'''
        # Secure the ProGear AI agent with Okta

        **Follow one delegated request from employee sign-in to a scoped Inventory token.**

        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:18px 0 8px">
          <span style="padding:8px 12px;border:1px solid #c7d2fe;border-radius:10px;background:#eef2ff"><b>Employee</b><br><small>signs in</small></span>
          <b>→</b>
          <span style="padding:8px 12px;border:1px solid #fed7aa;border-radius:10px;background:#fff7ed"><b>ProGear Agent</b><br><small>proves its identity</small></span>
          <b>→</b>
          <span style="padding:8px 12px;border:1px solid #bfdbfe;border-radius:10px;background:#eff6ff"><b>Okta ID-JAG</b><br><small>binds user + agent</small></span>
          <b>→</b>
          <span style="padding:8px 12px;border:1px solid #bbf7d0;border-radius:10px;background:#f0fdf4"><b>Inventory token</b><br><small>one resource + scope</small></span>
        </div>

        Use **Guided preview** with no credentials, or switch to **Live Okta** and run the same flow against a test org. Raw tokens and private keys are never displayed.
        '''
    ),
    markdown(
        r'''
        ## Setup

        Install two small libraries, then load the notebook helpers.
        '''
    ),
    code(
        r'''
        %pip -q install "PyJWT[crypto]>=2.8.0" "requests>=2.31.0"
        '''
    ),
    code(
        r'''
        import base64
        import hashlib
        import json
        import secrets
        import time
        import uuid
        from datetime import datetime, timezone
        from urllib.parse import parse_qs, urlencode, urlparse

        import jwt
        import requests
        from IPython.display import HTML, display
        from cryptography.hazmat.primitives.asymmetric import rsa
        from jwt.algorithms import RSAAlgorithm

        def b64url(raw: bytes) -> str:
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        def int_b64url(value: int) -> str:
            size = (value.bit_length() + 7) // 8
            return b64url(value.to_bytes(size, "big"))

        def public_jwk(private_key, kid: str) -> dict:
            numbers = private_key.public_key().public_numbers()
            return {
                "kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256",
                "n": int_b64url(numbers.n), "e": int_b64url(numbers.e),
            }

        def show_rows(title: str, rows: list[tuple[str, object]]) -> None:
            body = "".join(
                f"<tr><td style='padding:6px 12px;color:#475569'>{label}</td>"
                f"<td style='padding:6px 12px'><code>{str(value)}</code></td></tr>"
                for label, value in rows
            )
            display(HTML(
                f"<div style='border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;max-width:780px'>"
                f"<div style='padding:9px 12px;background:#f8fafc;font-weight:700'>{title}</div>"
                f"<table style='width:100%'>{body}</table></div>"
            ))

        def oauth_error(response: requests.Response, label: str) -> RuntimeError:
            try:
                body = response.json()
                code = body.get("error", "request_failed")
                detail = body.get("error_description", "Okta denied the request")
            except ValueError:
                code, detail = "request_failed", "Okta returned a non-JSON response"
            return RuntimeError(f"{label} ({response.status_code}, {code}): {detail}")

        print("Notebook helpers ready.")
        '''
    ),
    markdown(
        r'''
        ## 1. Connect your Okta org

        For a live run, add `USER_CLIENT_SECRET` (when your sign-in app requires it) and `AGENT_PRIVATE_JWK` to **Colab → Secrets**. Grant this notebook access; never paste either value into a cell.
        '''
    ),
    code(
        r'''
        # @title Choose preview or live Okta
        MODE = "Guided preview" # @param ["Guided preview", "Live Okta"]
        PREVIEW_EMPLOYEE = "Sarah Sales" # @param ["Sarah Sales", "Mike Manager"]
        OKTA_DOMAIN = "https://your-org.oktapreview.com" # @param {type:"string"}
        USER_CLIENT_ID = "your-sign-in-client-id" # @param {type:"string"}
        REDIRECT_URI = "http://localhost:8080/authorization-code/callback" # @param {type:"string"}
        CUSTOM_AS_ID = "your-inventory-authorization-server-id" # @param {type:"string"}
        RESOURCE_AUDIENCE = "api://progear-inventory" # @param {type:"string"}
        AGENT_CLIENT_ID = "your-workload-principal-id" # @param {type:"string"}
        AGENT_KEY_ID = "your-agent-key-id" # @param {type:"string"}
        REQUESTED_SCOPE = "inventory:read" # @param ["inventory:read", "inventory:write"]

        LIVE = MODE == "Live Okta"
        OKTA_DOMAIN = OKTA_DOMAIN.rstrip("/")
        CUSTOM_ISSUER = f"{OKTA_DOMAIN}/oauth2/{CUSTOM_AS_ID}"
        ORG_TOKEN_URL = f"{OKTA_DOMAIN}/oauth2/v1/token"
        CUSTOM_TOKEN_URL = f"{CUSTOM_ISSUER}/v1/token"

        USER_CLIENT_SECRET = None
        AGENT_PRIVATE_JWK = None
        if LIVE:
            placeholders = {
                "OKTA_DOMAIN": OKTA_DOMAIN,
                "USER_CLIENT_ID": USER_CLIENT_ID,
                "CUSTOM_AS_ID": CUSTOM_AS_ID,
                "AGENT_CLIENT_ID": AGENT_CLIENT_ID,
                "AGENT_KEY_ID": AGENT_KEY_ID,
            }
            missing = [name for name, value in placeholders.items() if "your-" in value]
            if missing:
                raise ValueError("Set these live values first: " + ", ".join(missing))
            try:
                from google.colab import userdata
                try:
                    USER_CLIENT_SECRET = userdata.get("USER_CLIENT_SECRET")
                except Exception:
                    USER_CLIENT_SECRET = None
                AGENT_PRIVATE_JWK = json.loads(userdata.get("AGENT_PRIVATE_JWK"))
            except ImportError as exc:
                raise RuntimeError("Live mode is designed for Google Colab Secrets.") from exc
            except Exception as exc:
                raise RuntimeError("Add a valid AGENT_PRIVATE_JWK JSON value to Colab Secrets.") from exc

        show_rows("Run configuration", [
            ("Mode", MODE),
            ("Employee", "chosen at Okta sign-in" if LIVE else PREVIEW_EMPLOYEE),
            ("Resource", RESOURCE_AUDIENCE),
            ("Requested scope", REQUESTED_SCOPE),
        ])
        '''
    ),
    markdown(
        r'''
        ## 2. Sign in to Okta

        Live mode opens the Org Authorization Server. After sign-in, copy the full localhost redirect URL—even if the page itself cannot load.
        '''
    ),
    code(
        r'''
        ID_TOKEN = None
        if LIVE:
            pkce_verifier = b64url(secrets.token_bytes(48))
            pkce_challenge = b64url(hashlib.sha256(pkce_verifier.encode()).digest())
            oauth_state = secrets.token_urlsafe(24)
            oauth_nonce = secrets.token_urlsafe(24)
            authorize_url = f"{OKTA_DOMAIN}/oauth2/v1/authorize?" + urlencode({
                "client_id": USER_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "response_mode": "query",
                "scope": "openid profile email",
                "state": oauth_state,
                "nonce": oauth_nonce,
                "prompt": "login",
                "code_challenge": pkce_challenge,
                "code_challenge_method": "S256",
            })
            display(HTML(
                f"<a href='{authorize_url}' target='_blank' style='display:inline-block;padding:11px 18px;"
                "background:#d95f18;color:white;border-radius:9px;text-decoration:none;font-weight:700'>"
                "Sign in with Okta</a>"
            ))
            print("Next: paste the full redirect URL into the cell below.")
        else:
            preview_org_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            preview_org_jwk = public_jwk(preview_org_key, "preview-org-key")
            preview_email = (
                "sarah.sales@example.com" if PREVIEW_EMPLOYEE == "Sarah Sales"
                else "mike.manager@example.com"
            )
            now = int(time.time())
            ID_TOKEN = jwt.encode(
                {
                    "sub": f"00u-preview-{PREVIEW_EMPLOYEE.split()[0].lower()}",
                    "email": preview_email,
                    "name": PREVIEW_EMPLOYEE,
                    "iss": "https://preview.okta.local",
                    "aud": "preview-sign-in-client",
                    "iat": now,
                    "exp": now + 600,
                },
                preview_org_key,
                algorithm="RS256",
                headers={"kid": "preview-org-key"},
            )
            print("Guided preview: a locally signed employee ID token is ready.")
        '''
    ),
    code(
        r'''
        # @title Finish the live sign-in
        REDIRECT_URL = "" # @param {type:"string"}

        if LIVE:
            if not REDIRECT_URL:
                raise ValueError("Paste the full redirect URL, then run this cell again.")
            query = parse_qs(urlparse(REDIRECT_URL).query)
            if query.get("state", [None])[0] != oauth_state:
                raise ValueError("OAuth state mismatch. Restart Step 2.")
            code_value = query.get("code", [None])[0]
            if not code_value:
                raise ValueError("The redirect URL does not contain an authorization code.")
            token_form = {
                "grant_type": "authorization_code",
                "client_id": USER_CLIENT_ID,
                "code": code_value,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": pkce_verifier,
            }
            basic_auth = (USER_CLIENT_ID, USER_CLIENT_SECRET) if USER_CLIENT_SECRET else None
            response = requests.post(ORG_TOKEN_URL, data=token_form, auth=basic_auth, timeout=15)
            if not response.ok:
                raise oauth_error(response, "User sign-in token exchange failed")
            token_response = response.json()
            ID_TOKEN = token_response["id_token"]
            print("Okta sign-in complete. The user ID token is held only in memory.")
        else:
            print("Preview sign-in complete.")
        '''
    ),
    markdown(
        r'''
        ## 3. Confirm the employee identity

        The user is the request subject. The ProGear agent will remain a separate identity.
        '''
    ),
    code(
        r'''
        if LIVE:
            signing_key = jwt.PyJWKClient(f"{OKTA_DOMAIN}/oauth2/v1/keys").get_signing_key_from_jwt(ID_TOKEN)
            id_claims = jwt.decode(
                ID_TOKEN,
                signing_key.key,
                algorithms=["RS256"],
                issuer=OKTA_DOMAIN,
                audience=USER_CLIENT_ID,
                options={"require": ["sub", "iss", "aud", "exp"]},
            )
            if id_claims.get("nonce") != oauth_nonce:
                raise ValueError("ID token nonce mismatch. Restart Step 2.")
        else:
            id_claims = jwt.decode(
                ID_TOKEN,
                jwt.PyJWK.from_dict(preview_org_jwk).key,
                algorithms=["RS256"],
                issuer="https://preview.okta.local",
                audience="preview-sign-in-client",
            )

        show_rows("Verified user ID token", [
            ("Employee", id_claims.get("name", "—")),
            ("Email", id_claims.get("email", "—")),
            ("Subject", id_claims["sub"]),
            ("Issuer", id_claims["iss"]),
            ("Expires", datetime.fromtimestamp(id_claims["exp"], timezone.utc).isoformat()),
        ])
        '''
    ),
    markdown(
        r'''
        ## 4. Prove the agent's identity

        The ProGear Agent is an Okta **Workload Principal** with its own key and lifecycle. This client assertion proves which agent is asking.
        '''
    ),
    code(
        r'''
        if LIVE:
            if AGENT_PRIVATE_JWK.get("kid") != AGENT_KEY_ID:
                raise ValueError("AGENT_KEY_ID must match the private JWK kid.")
            agent_signing_key = RSAAlgorithm.from_jwk(json.dumps(AGENT_PRIVATE_JWK))
        else:
            agent_signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            AGENT_CLIENT_ID = "wlp-preview-progear"
            AGENT_KEY_ID = "preview-agent-key"

        def build_client_assertion(audience: str) -> str:
            now = int(time.time())
            return jwt.encode(
                {
                    "iss": AGENT_CLIENT_ID,
                    "sub": AGENT_CLIENT_ID,
                    "aud": audience,
                    "iat": now,
                    "exp": now + 60,
                    "jti": str(uuid.uuid4()),
                },
                agent_signing_key,
                algorithm="RS256",
                headers={"kid": AGENT_KEY_ID},
            )

        org_client_assertion = build_client_assertion(ORG_TOKEN_URL)
        show_rows("Agent proof", [
            ("Workload Principal", AGENT_CLIENT_ID),
            ("Key", AGENT_KEY_ID),
            ("Algorithm", "RS256"),
            ("Audience", ORG_TOKEN_URL),
            ("Lifetime", "60 seconds"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 5. Request the ID-JAG

        Okta binds the signed-in employee, the registered agent, the target authorization server, and the requested scope into a short-lived Identity Assertion JWT Authorization Grant.
        '''
    ),
    code(
        r'''
        ID_JAG = None
        if LIVE:
            response = requests.post(
                ORG_TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": org_client_assertion,
                    "subject_token": ID_TOKEN,
                    "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
                    "requested_token_type": "urn:ietf:params:oauth:token-type:id-jag",
                    "scope": REQUESTED_SCOPE,
                    "audience": CUSTOM_ISSUER,
                },
                timeout=15,
            )
            if not response.ok:
                raise oauth_error(response, "ID-JAG exchange failed")
            result = response.json()
            ID_JAG = result["access_token"]
            id_jag_expires_in = result.get("expires_in", "short lived")
            id_jag_type = result.get("issued_token_type", "id-jag")
        else:
            now = int(time.time())
            ID_JAG = jwt.encode(
                {
                    "sub": id_claims["sub"],
                    "client_id": AGENT_CLIENT_ID,
                    "iss": "https://preview.okta.local",
                    "aud": "https://preview.okta.local/oauth2/inventory",
                    "scp": [REQUESTED_SCOPE],
                    "iat": now,
                    "exp": now + 120,
                    "jti": str(uuid.uuid4()),
                },
                preview_org_key,
                algorithm="RS256",
                headers={"kid": "preview-org-key"},
            )
            id_jag_expires_in = 120
            id_jag_type = "urn:ietf:params:oauth:token-type:id-jag"

        show_rows("ID-JAG issued", [
            ("Status", "Issued"),
            ("Type", id_jag_type),
            ("Expires in", f"{id_jag_expires_in} seconds"),
            ("Raw token", "kept in memory; not displayed"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 6. Verify employee + agent + target

        Read the identity chain—not the raw JWT.
        '''
    ),
    code(
        r'''
        expected_id_jag_audience = CUSTOM_ISSUER if LIVE else "https://preview.okta.local/oauth2/inventory"
        expected_id_jag_issuer = OKTA_DOMAIN if LIVE else "https://preview.okta.local"
        if LIVE:
            jag_key = jwt.PyJWKClient(f"{OKTA_DOMAIN}/oauth2/v1/keys").get_signing_key_from_jwt(ID_JAG)
            id_jag_claims = jwt.decode(
                ID_JAG,
                jag_key.key,
                algorithms=["RS256"],
                issuer=expected_id_jag_issuer,
                audience=expected_id_jag_audience,
                options={"require": ["sub", "iss", "aud", "exp"]},
            )
        else:
            id_jag_claims = jwt.decode(
                ID_JAG,
                jwt.PyJWK.from_dict(preview_org_jwk).key,
                algorithms=["RS256"],
                issuer=expected_id_jag_issuer,
                audience=expected_id_jag_audience,
            )

        delegated_agent = id_jag_claims.get("client_id", id_jag_claims.get("cid", "present in client context"))
        scopes = id_jag_claims.get("scp", id_jag_claims.get("scope", []))
        if isinstance(scopes, str):
            scopes = scopes.split()
        show_rows("Verified ID-JAG", [
            ("Employee subject", id_jag_claims["sub"]),
            ("Agent client", delegated_agent),
            ("Target", id_jag_claims["aud"]),
            ("Requested scope", ", ".join(scopes)),
            ("Expires", datetime.fromtimestamp(id_jag_claims["exp"], timezone.utc).isoformat()),
        ])
        '''
    ),
    markdown(
        r'''
        ## 7. Ask Inventory for a scoped token

        The Inventory Authorization Server now applies its policy to this **employee + agent + scope** request. The ID-JAG is one-time use.
        '''
    ),
    code(
        r'''
        RESOURCE_TOKEN = None
        POLICY_RESULT = None
        if LIVE:
            response = requests.post(
                CUSTOM_TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": build_client_assertion(CUSTOM_TOKEN_URL),
                    "assertion": ID_JAG,
                },
                timeout=15,
            )
            if response.ok:
                result = response.json()
                RESOURCE_TOKEN = result["access_token"]
                POLICY_RESULT = "Allowed — scoped resource token issued"
            else:
                try:
                    denied = response.json()
                    denial_code = denied.get("error", "access_denied")
                except ValueError:
                    denial_code = "access_denied"
                POLICY_RESULT = f"Denied — no resource token ({denial_code})"
        else:
            preview_allowed = REQUESTED_SCOPE == "inventory:read" or PREVIEW_EMPLOYEE == "Mike Manager"
            if preview_allowed:
                preview_resource_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                preview_resource_jwk = public_jwk(preview_resource_key, "preview-resource-key")
                now = int(time.time())
                RESOURCE_TOKEN = jwt.encode(
                    {
                        "sub": id_claims["sub"],
                        "act": {"sub": AGENT_CLIENT_ID},
                        "cid": AGENT_CLIENT_ID,
                        "iss": "https://preview.okta.local/oauth2/inventory",
                        "aud": RESOURCE_AUDIENCE,
                        "scp": [REQUESTED_SCOPE],
                        "iat": now,
                        "exp": now + 300,
                    },
                    preview_resource_key,
                    algorithm="RS256",
                    headers={"kid": "preview-resource-key"},
                )
                POLICY_RESULT = "Allowed — scoped resource token issued"
            else:
                POLICY_RESULT = "Denied — Sales has read-only Inventory access"

        show_rows("Inventory policy result", [
            ("Employee", id_claims.get("email", id_claims["sub"])),
            ("Requested scope", REQUESTED_SCOPE),
            ("Decision", POLICY_RESULT),
            ("Raw token", "kept in memory; not displayed" if RESOURCE_TOKEN else "not issued"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 8. Verify before calling the API

        The resource accepts only a valid signature, issuer, audience, expiry, and required scope.
        '''
    ),
    code(
        r'''
        if RESOURCE_TOKEN:
            expected_resource_issuer = CUSTOM_ISSUER if LIVE else "https://preview.okta.local/oauth2/inventory"
            if LIVE:
                resource_key = jwt.PyJWKClient(f"{CUSTOM_ISSUER}/v1/keys").get_signing_key_from_jwt(RESOURCE_TOKEN)
                resource_claims = jwt.decode(
                    RESOURCE_TOKEN,
                    resource_key.key,
                    algorithms=["RS256"],
                    issuer=expected_resource_issuer,
                    audience=RESOURCE_AUDIENCE,
                    options={"require": ["sub", "iss", "aud", "exp"]},
                )
            else:
                resource_claims = jwt.decode(
                    RESOURCE_TOKEN,
                    jwt.PyJWK.from_dict(preview_resource_jwk).key,
                    algorithms=["RS256"],
                    issuer=expected_resource_issuer,
                    audience=RESOURCE_AUDIENCE,
                )
            granted_scopes = resource_claims.get("scp", resource_claims.get("scope", []))
            if isinstance(granted_scopes, str):
                granted_scopes = granted_scopes.split()
            if REQUESTED_SCOPE not in granted_scopes:
                raise ValueError(f"Resource token is missing {REQUESTED_SCOPE}.")
            actor = resource_claims.get("act", {}).get("sub", resource_claims.get("cid", "—"))
            show_rows("Resource token accepted", [
                ("Employee subject", resource_claims["sub"]),
                ("Agent actor", actor),
                ("Audience", resource_claims["aud"]),
                ("Granted scope", ", ".join(granted_scopes)),
                ("Decision", "The Inventory API may now evaluate the business action"),
            ])
        else:
            print("No resource token exists. The protected Inventory call must not run.")
        '''
    ),
    markdown(
        r'''
        ## 9. Read the ProGear result

        | Employee | Requested scope | Token result |
        |---|---|---|
        | Sarah Sales | `inventory:read` | Issued |
        | Sarah Sales | `inventory:write` | Denied; contact a manager |
        | Mike Manager | `inventory:write` | Issued |

        **On vacation** is a separate delegation stop: when true, the application stops before Step 5, so no ID-JAG is requested. Quantity rules, FGA, and VP approval stay in the ProGear web demo—not this beginner notebook.
        '''
    ),
    markdown(
        r'''
        ## 10. Find the audit proof

        In the Okta Admin Console, open **Reports → System Log** and filter for token grant events. Match the employee, agent client, target authorization server, scope, time, and outcome.

        | Evidence | What it answers |
        |---|---|
        | User sign-in | Who started the request? |
        | ID-JAG grant | Which governed agent acted for that user? |
        | Resource token grant or denial | Which resource and scope did policy allow? |
        '''
    ),
    markdown(
        r'''
        ## Done

        You followed the complete chain:

        **employee sign-in → verified ID token → agent proof → ID-JAG → resource policy → verified scoped token**

        The employee never became the agent. The agent never received the employee's password. Inventory received only the access its authorization server approved.

        ### References

        - [Set up AI agent token exchange](https://developer.okta.com/docs/guides/ai-agent-token-exchange/-/main/)
        - [Okta for AI Agents](https://developer.okta.com/docs/api/secures-ai)
        - [IETF Identity Assertion JWT Authorization Grant](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant)
        - [Cross App Access](https://xaa.dev/)
        - [ProGear platform-neutral exchange helper](../examples/token_exchange.py)
        '''
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "colab": {
            "name": "ProGear — Okta Cross-App Access walkthrough",
            "provenance": [],
        },
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


OUTPUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
print(f"Wrote {OUTPUT} ({len(cells)} cells)")
