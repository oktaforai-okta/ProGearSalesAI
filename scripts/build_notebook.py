#!/usr/bin/env python3
"""Build the customer-owned agent Cross-App Access Colab notebook."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "progear-inventory-authorization-story.ipynb"


def _source(value: str) -> list[str]:
    return dedent(value).strip("\n").splitlines(keepends=True)


def markdown(value: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _source(value)}


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
        # Wire your custom AI agent to Okta

        **Give an agent its own identity, let it act for a signed-in user, and issue one scoped token for one protected resource.**

        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:18px 0 8px">
          <span style="padding:8px 12px;border:1px solid #c7d2fe;border-radius:10px;background:#eef2ff"><b>Your app</b><br><small>signs in a user</small></span>
          <b>→</b>
          <span style="padding:8px 12px;border:1px solid #fed7aa;border-radius:10px;background:#fff7ed"><b>Your agent</b><br><small>Workload Principal</small></span>
          <b>→</b>
          <span style="padding:8px 12px;border:1px solid #bfdbfe;border-radius:10px;background:#eff6ff"><b>Okta ID-JAG</b><br><small>user + agent + target</small></span>
          <b>→</b>
          <span style="padding:8px 12px;border:1px solid #bbf7d0;border-radius:10px;background:#f0fdf4"><b>Your MCP server</b><br><small>discovery + scoped tool call</small></span>
        </div>

        ProGear is the worked example. Replace its names with your agent, API, audience, and scope. No FGA or approval workflow is required for this walkthrough.
        '''
    ),
    markdown(
        r'''
        ## Start with your architecture

        You bring three components. Okta adds the identity and delegation layer around them.

        | You already have | Okta configuration | Runtime result |
        |---|---|---|
        | User-facing app | OIDC sign-in app linked to the agent | Verified user ID token |
        | Custom agent runtime | Registered AI agent + public key | Agent authenticates as itself |
        | Protected MCP server | Registered MCP resource + one Custom Authorization Server | Short-lived token sent in `tools/call` |
        '''
    ),
    code(
        r'''
        # @title Name your first integration
        OKTA_DOMAIN = "https://your-org.oktapreview.com" # @param {type:"string"}
        AGENT_NAME = "My Custom Agent" # @param {type:"string"}
        RESOURCE_NAME = "ProGear Inventory MCP" # @param {type:"string"}
        RESOURCE_URL = "https://progear-mcp-servers-m2f3.onrender.com/inventory/mcp" # @param {type:"string"}
        RESOURCE_AUDIENCE = "api://progear-inventory" # @param {type:"string"}
        RESOURCE_SCOPE = "inventory:read" # @param {type:"string"}
        MCP_TOOL_NAME = "get_inventory_summary" # @param {type:"string"}
        MCP_TOOL_ARGUMENTS = "{}" # @param {type:"string"}
        REDIRECT_URI = "http://localhost:8080/authorization-code/callback" # @param {type:"string"}

        print(f"Okta org:  {OKTA_DOMAIN}")
        print(f"Agent:     {AGENT_NAME}")
        print(f"Resource:  {RESOURCE_NAME}")
        print(f"MCP URL:   {RESOURCE_URL}")
        print(f"Audience:  {RESOURCE_AUDIENCE}")
        print(f"Scope:     {RESOURCE_SCOPE}")
        print(f"Tool:      {MCP_TOOL_NAME} {MCP_TOOL_ARGUMENTS}")
        print(f"Callback:  {REDIRECT_URI}")
        '''
    ),
    markdown(
        r'''
        # Part 1 — Configure Okta once

        These are control-plane steps. They create the trust boundary your agent code will use at runtime. This notebook does **not** silently create tenant objects.

        **Before you begin:** use a test org subscribed to Okta for AI Agents, an admin who can manage agents/apps/authorization servers, API Access Management for the Custom Authorization Server, and one assigned test user.
        '''
    ),
    markdown(
        r'''
        ## 1. Create the user sign-in app

        **Purpose:** identify the human asking your agent to act.

        | Admin setting | Use this value |
        |---|---|
        | Menu | **Applications → Applications → Create App Integration** |
        | Sign-in method | **OIDC – OpenID Connect** |
        | Application type | The type that matches your app; use **Web Application** for this Colab walkthrough |
        | Grant type | **Authorization Code**; use PKCE |
        | Sign-in redirect URI | The `REDIRECT_URI` from the planning cell |
        | Assignments | Your test user or test group |

        **Save:** Client ID. If the web app uses a client secret, add it to Colab Secrets as `USER_CLIENT_SECRET`.

        Use the **Org Authorization Server** for this sign-in. The resulting ID token is the employee identity presented during Cross-App Access.

        **Official help:** [Create an OIDC app integration](https://help.okta.com/en-us/Content/Topics/Apps/Apps_App_Integration_Wizard_OIDC.htm) · [Authorization Code with PKCE](https://developer.okta.com/docs/guides/implement-grant-type/authcodepkce/main/)
        '''
    ),
    markdown(
        r'''
        ## 2. Register your custom agent

        **Purpose:** make the agent a managed identity instead of hiding it inside the user's session.

        | Agent setting | Use this value |
        |---|---|
        | Menu | **Directory → AI Agents → Register AI agent → Register manually** |
        | Name | `AGENT_NAME` from the planning cell |
        | Owners | At least two accountable owners |
        | Credentials | Add and activate a **public JWK** |
        | Delegations → User sign-on | OIDC app from Step 1 |
        | Delegation authorization server | **Okta Org Authorization Server** |

        **Save:** Workload Principal/client ID, key ID, and the private JWK. Put the private JWK in Colab Secrets as `AGENT_PRIVATE_JWK`; never paste it into notebook source.

        Okta can now distinguish the user (`sub`) from the agent client acting for that user.

        **Official help:** [Add a custom AI agent manually](https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-add-manually.htm) · [Build a private-key client assertion](https://developer.okta.com/docs/guides/build-self-signed-jwt/main/)
        '''
    ),
    markdown(
        r'''
        ## 3. Create one Custom Authorization Server

        **Purpose:** give your protected resource its own token issuer and policy boundary.

        | Server setting | Use this value |
        |---|---|
        | Menu | **Security → API → Authorization Servers → Add Authorization Server** |
        | Name | `RESOURCE_NAME` + “Authorization Server” |
        | Audience | `RESOURCE_AUDIENCE` from the planning cell |
        | Description | What API or MCP server this boundary protects |

        **Save:** the issuer URI. Your MCP server publishes that URI in its protected-resource metadata, so the agent runtime does not need a copied authorization-server ID.

        One server is enough for this walkthrough. Add more only when you truly need separate security domains.

        **Official help:** [Create an authorization server](https://help.okta.com/en-us/Content/Topics/Security/api-config-auth-server.htm) · [Understand authorization-server boundaries](https://help.okta.com/en-us/content/topics/security/api-build-oauth-servers.htm)
        '''
    ),
    markdown(
        r'''
        ## 4. Add one scope and one policy

        **Purpose:** describe the smallest action the agent may request, then decide who may receive it.

        | Configuration | Use this value |
        |---|---|
        | **Scopes → Add Scope** | `RESOURCE_SCOPE` from the planning cell |
        | User consent | **Implicit** for this controlled test |
        | **Access Policies → Add Policy** | Assign it to your AI agent client |
        | Rule grant type | **JWT Bearer** |
        | Rule user | A user assigned to the sign-in app |
        | Rule scopes | Only `RESOURCE_SCOPE` |
        | Token lifetime | Short enough for your test and risk model |

        **Check:** the policy and its rule are both Active. An inactive or mismatched rule produces `no_matching_policy`.

        Start with one read scope. A second scope is useful later when you want to demonstrate a denial.

        **Official help:** [Create API scopes](https://help.okta.com/en-us/Content/Topics/Security/api-config-scopes.htm) · [Create access policies and rules](https://help.okta.com/en-us/content/topics/security/api-config-access-policies.htm)
        '''
    ),
    markdown(
        r'''
        ## 5. Register the MCP server and connect the agent for XAA

        **Purpose:** cap the agent's maximum downstream access.

        | Connection setting | Use this value |
        |---|---|
        | Register resource | **AI Agent Governance → Resources → MCP servers → Add MCP server** |
        | MCP server URL | `RESOURCE_URL` from the planning cell |
        | Connect agent | **Directory → AI Agents → your agent → Resource connections** |
        | Resource type | **Authorization server** |
        | Authorization server | The Custom Authorization Server from Step 3 |
        | Resource indicator | `RESOURCE_AUDIENCE` |
        | Scope control | **Only allow** |
        | Allowed scope | `RESOURCE_SCOPE` |

        **Check:** activate the resource connection, its credential, and the AI agent. A deactivated agent cannot start a new exchange.

        The MCP registration gives Okta standards-based inventory and discovery for the protected endpoint. The **Authorization server** connection keeps this walkthrough on native Cross-App Access (`IDENTITY_ASSERTION_CUSTOM_AS`): it says what the agent may request, and the authorization-server policy decides whether this user receives it.

        Do not replace this XAA connection with an **MCP server** connection for this walkthrough. That connection type uses the STS access-token model in the current Okta resource-connection API; it is useful for OAuth-connected third-party MCP services, but it is not the ID-JAG flow being demonstrated here.

        The MCP server must expose `/.well-known/oauth-protected-resource/...` metadata that names the Step 3 authorization server and supported scope.

        **Official help:** [Add MCP servers](https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-mcp-server.htm) · [Connect AI agents to resources](https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-connected-resource.htm) · [Secure MCP servers](https://developer.okta.com/docs/api/secures-ai/mcp-servers)
        '''
    ),
    markdown(
        r'''
        ### Configuration receipt — record it once

        If these objects already exist, use their current values. Otherwise, record the identifiers as you complete Steps 1–5.

        | Value | Created in |
        |---|---|
        | Okta domain | Your Okta org |
        | Sign-in client ID + redirect URI | OIDC app |
        | Agent client ID + key ID + private JWK | AI agent registration |
        | MCP URL | Registered MCP server |
        | Audience + scope | MCP server and authorization-server configuration |

        You already entered the MCP URL, audience, scope, redirect URI, agent, and resource. Enter only the identifiers Okta generated for sign-in and the agent. The runtime discovers the target authorization server from the MCP URL.
        '''
    ),
    code(
        r'''
        # @title Record the Okta-generated IDs once
        MODE = "Guided preview" # @param ["Guided preview", "Live Okta"]
        SIGN_IN_CLIENT_ID_INPUT = "your-sign-in-client-id" # @param {type:"string"}
        AGENT_CLIENT_ID_INPUT = "your-workload-principal-id" # @param {type:"string"}
        AGENT_KEY_ID_INPUT = "your-agent-key-id" # @param {type:"string"}
        PREVIEW_USER_EMAIL = "alex@example.com" # @param {type:"string"}
        PREVIEW_POLICY = "Allow requested scope" # @param ["Allow requested scope", "Deny requested scope"]

        print(f"Mode:   {MODE}")
        print("Saved. The runtime will reuse this receipt; these values are not entered again.")
        '''
    ),
    markdown(
        r'''
        # Part 2 — Wire your agent runtime

        The two exchanges belong in trusted backend code, outside the model prompt and tool arguments.

        ```text
        browser/app ── ID token ──▶ agent backend
                                      │ agent private key
                                      ▼
        Okta Org AS ── ID-JAG ──▶ Custom Authorization Server
                                      │ scoped access token
                                      ▼
                                protected resource
        ```

        Use **Guided preview** without credentials or select **Live Okta** after completing Part 1. Raw tokens and private keys are never displayed.
        '''
    ),
    markdown(
        r'''
        ## Runtime setup
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
        import os
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
                f"<div style='border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;max-width:820px'>"
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

        def protected_resource_metadata_url(resource_url: str) -> str:
            parsed = urlparse(resource_url.rstrip("/"))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("RESOURCE_URL must be an absolute HTTP URL.")
            return (
                f"{parsed.scheme}://{parsed.netloc}"
                f"/.well-known/oauth-protected-resource{parsed.path}"
            )

        print("Runtime helpers ready.")
        '''
    ),
    markdown(
        r'''
        ## Load the saved configuration

        This cell automatically combines the choices from the planning cell with the Okta-generated identifiers in the receipt. Live mode loads only sensitive values from Colab Secrets: `AGENT_PRIVATE_JWK` and, when needed, `USER_CLIENT_SECRET`. Local and CI checks may provide the same names as environment variables.
        '''
    ),
    code(
        r'''
        LIVE = MODE == "Live Okta"
        SIGN_IN_CLIENT_ID = SIGN_IN_CLIENT_ID_INPUT
        AGENT_CLIENT_ID = AGENT_CLIENT_ID_INPUT
        AGENT_KEY_ID = AGENT_KEY_ID_INPUT
        USER_CLIENT_SECRET = None
        AGENT_PRIVATE_JWK = None

        if LIVE:
            try:
                from google.colab import userdata
            except ImportError:
                userdata = None

            def optional_secret(name: str) -> str | None:
                if userdata is not None:
                    try:
                        value = userdata.get(name)
                    except Exception:
                        value = None
                    if value:
                        return value
                return os.environ.get(name)

            def required_secret(name: str) -> str:
                value = optional_secret(name)
                if not value:
                    raise RuntimeError(
                        f"Add {name} to Colab Secrets or provide it as an environment variable."
                    )
                return value

            USER_CLIENT_SECRET = optional_secret("USER_CLIENT_SECRET")
            try:
                AGENT_PRIVATE_JWK = json.loads(required_secret("AGENT_PRIVATE_JWK"))
            except json.JSONDecodeError as exc:
                raise RuntimeError("AGENT_PRIVATE_JWK must contain valid JSON.") from exc

        OKTA_DOMAIN = OKTA_DOMAIN.rstrip("/")
        ORG_TOKEN_URL = f"{OKTA_DOMAIN}/oauth2/v1/token"
        METADATA_URL = protected_resource_metadata_url(RESOURCE_URL)
        if LIVE:
            metadata_response = requests.get(METADATA_URL, timeout=15)
            if not metadata_response.ok:
                raise oauth_error(metadata_response, "MCP discovery failed")
            protected_resource = metadata_response.json()
            if protected_resource.get("resource", "").rstrip("/") != RESOURCE_URL.rstrip("/"):
                raise ValueError("MCP metadata identifies a different resource URL.")
            advertised_scopes = protected_resource.get("scopes_supported", [])
            if RESOURCE_SCOPE not in advertised_scopes:
                raise ValueError(f"MCP metadata does not advertise {RESOURCE_SCOPE}.")
            matching_issuers = [
                value.rstrip("/")
                for value in protected_resource.get("authorization_servers", [])
                if value.rstrip("/").startswith(f"{OKTA_DOMAIN}/oauth2/")
            ]
            if len(matching_issuers) != 1:
                raise ValueError("MCP metadata must name exactly one authorization server in this Okta org.")
            CUSTOM_ISSUER = matching_issuers[0]
        else:
            CUSTOM_ISSUER = "https://preview.okta.local/oauth2/resource"
        CUSTOM_TOKEN_URL = f"{CUSTOM_ISSUER}/v1/token"

        if LIVE:
            values = {
                "OKTA_DOMAIN": OKTA_DOMAIN,
                "SIGN_IN_CLIENT_ID": SIGN_IN_CLIENT_ID,
                "AGENT_CLIENT_ID": AGENT_CLIENT_ID,
                "AGENT_KEY_ID": AGENT_KEY_ID,
            }
            missing = [name for name, value in values.items() if "your-" in value]
            if missing:
                raise ValueError("Complete these values first: " + ", ".join(missing))

        show_rows("Runtime map", [
            ("Mode", MODE),
            ("Agent", AGENT_NAME),
            ("Agent client", AGENT_CLIENT_ID if LIVE else "wlp-preview-custom-agent"),
            ("Resource", RESOURCE_NAME),
            ("MCP URL", RESOURCE_URL),
            ("Well-known", METADATA_URL),
            ("Audience", RESOURCE_AUDIENCE),
            ("Scope", RESOURCE_SCOPE),
            ("Authorization server", CUSTOM_ISSUER),
        ])
        '''
    ),
    markdown(
        r'''
        ## 6. Authenticate the user

        Your app signs the user in through the Org Authorization Server. The agent backend receives a verified ID token—not the user's password.
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
                "client_id": SIGN_IN_CLIENT_ID,
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
            print("After sign-in, copy the full redirect URL into the next cell.")
        else:
            preview_org_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            preview_org_jwk = public_jwk(preview_org_key, "preview-org-key")
            now = int(time.time())
            ID_TOKEN = jwt.encode(
                {
                    "sub": "00u-preview-user",
                    "email": PREVIEW_USER_EMAIL,
                    "name": "Preview User",
                    "iss": "https://preview.okta.local",
                    "aud": "preview-sign-in-client",
                    "iat": now,
                    "exp": now + 600,
                },
                preview_org_key,
                algorithm="RS256",
                headers={"kid": "preview-org-key"},
            )
            print("Guided preview: a locally signed user ID token is ready.")
        '''
    ),
    code(
        r'''
        # @title Complete the live redirect
        REDIRECT_URL = "" # @param {type:"string"}

        if LIVE:
            if not REDIRECT_URL:
                raise ValueError("Paste the full redirect URL, then run this cell again.")
            query = parse_qs(urlparse(REDIRECT_URL).query)
            if query.get("state", [None])[0] != oauth_state:
                raise ValueError("OAuth state mismatch. Restart Step 6.")
            authorization_code = query.get("code", [None])[0]
            if not authorization_code:
                raise ValueError("The redirect URL does not contain an authorization code.")
            form = {
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": pkce_verifier,
            }
            if USER_CLIENT_SECRET:
                basic_auth = (SIGN_IN_CLIENT_ID, USER_CLIENT_SECRET)
            else:
                basic_auth = None
                form["client_id"] = SIGN_IN_CLIENT_ID
            response = requests.post(ORG_TOKEN_URL, data=form, auth=basic_auth, timeout=15)
            if not response.ok:
                raise oauth_error(response, "User sign-in exchange failed")
            ID_TOKEN = response.json()["id_token"]
            print("User sign-in complete. The ID token is held only in memory.")
        else:
            print("Preview sign-in complete.")
        '''
    ),
    code(
        r'''
        if LIVE:
            user_key = jwt.PyJWKClient(f"{OKTA_DOMAIN}/oauth2/v1/keys").get_signing_key_from_jwt(ID_TOKEN)
            user_claims = jwt.decode(
                ID_TOKEN,
                user_key.key,
                algorithms=["RS256"],
                issuer=OKTA_DOMAIN,
                audience=SIGN_IN_CLIENT_ID,
                options={"require": ["sub", "iss", "aud", "exp"]},
            )
            if user_claims.get("nonce") != oauth_nonce:
                raise ValueError("ID token nonce mismatch. Restart Step 6.")
        else:
            user_claims = jwt.decode(
                ID_TOKEN,
                jwt.PyJWK.from_dict(preview_org_jwk).key,
                algorithms=["RS256"],
                issuer="https://preview.okta.local",
                audience="preview-sign-in-client",
            )

        show_rows("Verified user identity", [
            ("Name", user_claims.get("name", "—")),
            ("Email", user_claims.get("email", "—")),
            ("Subject", user_claims["sub"]),
            ("Issuer", user_claims["iss"]),
            ("Raw token", "kept in memory; not displayed"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 7. Authenticate the agent

        The backend signs a short-lived `private_key_jwt` assertion with the agent's private key. Okta verifies it with the public key registered in Step 2.
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
            AGENT_CLIENT_ID = "wlp-preview-custom-agent"
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
            ("Agent", AGENT_NAME),
            ("Workload Principal", AGENT_CLIENT_ID),
            ("Key", AGENT_KEY_ID),
            ("Token endpoint", ORG_TOKEN_URL),
            ("Assertion lifetime", "60 seconds"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 8. Request an ID-JAG

        The agent presents the user's ID token and its own client assertion. Okta issues a short-lived ID-JAG for this **user + agent + target + scope**.

        **Protocol reference:** [Set up AI agent token exchange](https://developer.okta.com/docs/guides/ai-agent-token-exchange/-/main/)
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
                    "scope": RESOURCE_SCOPE,
                    "audience": CUSTOM_ISSUER,
                },
                timeout=15,
            )
            if not response.ok:
                raise oauth_error(response, "ID-JAG exchange failed")
            result = response.json()
            ID_JAG = result["access_token"]
            id_jag_lifetime = result.get("expires_in", "short lived")
        else:
            preview_target = "https://preview.okta.local/oauth2/resource"
            now = int(time.time())
            ID_JAG = jwt.encode(
                {
                    "sub": user_claims["sub"],
                    "client_id": AGENT_CLIENT_ID,
                    "iss": "https://preview.okta.local",
                    "aud": preview_target,
                    "scp": [RESOURCE_SCOPE],
                    "iat": now,
                    "exp": now + 120,
                    "jti": str(uuid.uuid4()),
                },
                preview_org_key,
                algorithm="RS256",
                headers={"kid": "preview-org-key"},
            )
            id_jag_lifetime = 120

        show_rows("ID-JAG issued", [
            ("User", user_claims["sub"]),
            ("Agent", AGENT_CLIENT_ID),
            ("Target", CUSTOM_ISSUER if LIVE else preview_target),
            ("Requested scope", RESOURCE_SCOPE),
            ("Expires in", f"{id_jag_lifetime} seconds"),
            ("Raw ID-JAG", "kept in memory; not displayed"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 9. Exchange the ID-JAG for a resource token

        Your Custom Authorization Server applies its policy. If allowed, it consumes the one-time ID-JAG and returns an access token for your audience and scope.
        '''
    ),
    code(
        r'''
        RESOURCE_TOKEN = None
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
                RESOURCE_TOKEN = response.json()["access_token"]
                POLICY_RESULT = "Allowed — scoped resource token issued"
            else:
                try:
                    error_code = response.json().get("error", "access_denied")
                except ValueError:
                    error_code = "access_denied"
                POLICY_RESULT = f"Denied — no resource token ({error_code})"
        elif PREVIEW_POLICY == "Allow requested scope":
            preview_resource_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            preview_resource_jwk = public_jwk(preview_resource_key, "preview-resource-key")
            now = int(time.time())
            RESOURCE_TOKEN = jwt.encode(
                {
                    "sub": user_claims["sub"],
                    "act": {"sub": AGENT_CLIENT_ID},
                    "cid": AGENT_CLIENT_ID,
                    "iss": preview_target,
                    "aud": RESOURCE_AUDIENCE,
                    "scp": [RESOURCE_SCOPE],
                    "iat": now,
                    "exp": now + 300,
                },
                preview_resource_key,
                algorithm="RS256",
                headers={"kid": "preview-resource-key"},
            )
            POLICY_RESULT = "Allowed — scoped resource token issued"
        else:
            POLICY_RESULT = "Denied — resource policy rejected the request"

        show_rows("Resource authorization", [
            ("Authorization Server", CUSTOM_ISSUER if LIVE else preview_target),
            ("Audience", RESOURCE_AUDIENCE),
            ("Scope", RESOURCE_SCOPE),
            ("Decision", POLICY_RESULT),
            ("Raw access token", "kept in memory; not displayed" if RESOURCE_TOKEN else "not issued"),
        ])
        '''
    ),
    markdown(
        r'''
        ## 10. Validate the token and call the MCP tool

        The MCP resource—not the model—must validate the token's signature, issuer, audience, expiry, and scope before doing any work. The client then uses the standard JSON-RPC `tools/call` method.
        '''
    ),
    code(
        r'''
        if RESOURCE_TOKEN:
            expected_issuer = CUSTOM_ISSUER if LIVE else preview_target
            if LIVE:
                resource_key = jwt.PyJWKClient(f"{CUSTOM_ISSUER}/v1/keys").get_signing_key_from_jwt(RESOURCE_TOKEN)
                resource_claims = jwt.decode(
                    RESOURCE_TOKEN,
                    resource_key.key,
                    algorithms=["RS256"],
                    issuer=expected_issuer,
                    audience=RESOURCE_AUDIENCE,
                    options={"require": ["sub", "iss", "aud", "exp"]},
                )
            else:
                resource_claims = jwt.decode(
                    RESOURCE_TOKEN,
                    jwt.PyJWK.from_dict(preview_resource_jwk).key,
                    algorithms=["RS256"],
                    issuer=expected_issuer,
                    audience=RESOURCE_AUDIENCE,
                )
            granted_scopes = resource_claims.get("scp", resource_claims.get("scope", []))
            if isinstance(granted_scopes, str):
                granted_scopes = granted_scopes.split()
            if RESOURCE_SCOPE not in granted_scopes:
                raise ValueError(f"Resource token is missing {RESOURCE_SCOPE}.")
            actor = resource_claims.get("act", {}).get("sub", resource_claims.get("cid", "—"))
            show_rows("Resource token accepted", [
                ("User subject", resource_claims["sub"]),
                ("Agent actor", actor),
                ("Audience", resource_claims["aud"]),
                ("Granted scope", ", ".join(granted_scopes)),
                ("Expires", datetime.fromtimestamp(resource_claims["exp"], timezone.utc).isoformat()),
            ])
            if LIVE:
                try:
                    tool_arguments = json.loads(MCP_TOOL_ARGUMENTS)
                except json.JSONDecodeError as exc:
                    raise ValueError("MCP_TOOL_ARGUMENTS must be a JSON object.") from exc
                if not isinstance(tool_arguments, dict):
                    raise ValueError("MCP_TOOL_ARGUMENTS must be a JSON object.")
                rpc_id = str(uuid.uuid4())
                api_response = requests.post(
                    RESOURCE_URL,
                    headers={
                        "Authorization": f"Bearer {RESOURCE_TOKEN}",
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "method": "tools/call",
                        "params": {"name": MCP_TOOL_NAME, "arguments": tool_arguments},
                    },
                    timeout=15,
                )
                print(f"MCP tools/call response: HTTP {api_response.status_code}")
                if not api_response.ok:
                    raise oauth_error(api_response, "MCP tool call failed")
            else:
                print(f"Preview: would call MCP tool {MCP_TOOL_NAME} with a Bearer token.")
        else:
            print("No resource token exists. Your agent must not call the protected resource.")
        '''
    ),
    markdown(
        r'''
        # Part 3 — Put the pattern into your agent

        Keep the identity code around the agent—not inside the prompt.

        ```python
        # Trusted backend boundary
        user_id_token = signed_in_session.id_token
        metadata = discover_oauth_protected_resource(mcp_url)
        id_jag = okta.exchange_user_token(
            user_id_token=user_id_token,
            audience=metadata.authorization_servers[0],
            scope=required_scope,
        )
        access_token = okta.exchange_id_jag(id_jag)
        verify_access_token(access_token, audience, required_scope)

        # Only now may the tool call the resource
        result = mcp.tools_call(access_token=access_token, name=tool_name, arguments=args)
        ```

        | Component | Responsibility |
        |---|---|
        | Browser or client | Sign in the user and protect the session |
        | Agent backend | Hold the private key and perform both exchanges |
        | MCP resource | Publish RFC 9728 metadata, validate tokens, and enforce tool scopes |
        | Okta | Govern the agent, delegation, resource connection, policy, and audit evidence |

        The repository's reusable implementation is [`examples/token_exchange.py`](../examples/token_exchange.py).
        '''
    ),
    markdown(
        r'''
        ## Test the security boundary

        1. **Allowed:** request the configured scope and confirm a resource token is issued.
        2. **Denied:** request a scope outside the resource connection or policy and confirm no resource token is issued.
        3. **Agent cutoff:** deactivate the AI agent and confirm new exchanges stop.
        4. **Resource validation:** change the expected audience or scope and confirm the API rejects the token.

        Do not test with a write endpoint until the identity and denial paths are correct.
        '''
    ),
    markdown(
        r'''
        ## Find the audit proof

        Open **Reports → System Log** and match the user, agent client, target authorization server, requested scope, time, and outcome.

        **Official help:** [Use the System Log](https://help.okta.com/oie/en-us/content/topics/reports/reports_syslog.htm)
        '''
    ),
    markdown(
        r'''
        ## ProGear as the completed example

        | Your design choice | ProGear value |
        |---|---|
        | Custom agent | ProGear Sales Agent |
        | Protected resource | ProGear Inventory MCP |
        | MCP URL | `https://progear-mcp-servers-m2f3.onrender.com/inventory/mcp` |
        | Discovery | `/.well-known/oauth-protected-resource/inventory/mcp` |
        | One authorization server | ProGear Inventory MCP Custom Authorization Server |
        | Audience | `api://progear-inventory` |
        | First scope | `inventory:read` |

        After this basic integration works, you can add another scope, user-context rules, FGA, or human approval. Those are extensions—not prerequisites for Cross-App Access.
        '''
    ),
    markdown(
        r'''
        ## Done

        You configured and wired the complete path:

        **OIDC sign-in → registered agent identity → MCP discovery → ID-JAG → scoped token → native MCP tools/call**

        ### Core references

        - [Okta for AI Agents](https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agents-home.htm)
        - [Register a custom AI agent](https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-add-manually.htm)
        - [Connect an AI agent to resources](https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-connected-resource.htm)
        - [Set up AI agent token exchange](https://developer.okta.com/docs/guides/ai-agent-token-exchange/-/main/)
        - [Secure MCP servers with Okta](https://developer.okta.com/docs/api/secures-ai/mcp-servers)
        - [RFC 9728 OAuth Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728)
        - [IETF Identity Assertion JWT Authorization Grant](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant)
        - [Cross App Access](https://xaa.dev/)
        '''
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "colab": {
            "name": "Wire your custom AI agent to Okta",
            "provenance": [],
        },
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


OUTPUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
print(f"Wrote {OUTPUT} ({len(cells)} cells)")
