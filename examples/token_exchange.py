"""Platform-neutral Okta token exchange helpers for customer-owned AI agents.

Turns a signed-in user's ID token into a scoped access token:

    id_token -> ID-JAG (Org Authorization Server)
             -> access_token (Custom Authorization Server)

This example reads secrets from environment variables. In production, inject
private key material from your platform's secrets manager and never log tokens.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
import requests
from jwt.algorithms import RSAAlgorithm

TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
ID_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:id_token"
ID_JAG_TYPE = "urn:ietf:params:oauth:token-type:id-jag"


@dataclass(frozen=True)
class TokenExchangeConfig:
    okta_domain: str
    custom_authorization_server_id: str
    requested_scope: str
    resource_audience: str
    agent_client_id: str
    agent_key_id: str
    agent_private_key_jwk: dict[str, Any]
    timeout_seconds: int = 10

    @property
    def org_token_url(self) -> str:
        return f"{self.okta_domain.rstrip('/')}/oauth2/v1/token"

    @property
    def custom_authorization_server_issuer(self) -> str:
        return (
            f"{self.okta_domain.rstrip('/')}/oauth2/"
            f"{self.custom_authorization_server_id}"
        )

    @property
    def custom_authorization_server_token_url(self) -> str:
        return f"{self.custom_authorization_server_issuer}/v1/token"

    @property
    def custom_authorization_server_keys_url(self) -> str:
        return f"{self.custom_authorization_server_issuer}/v1/keys"

    @classmethod
    def from_environment(cls) -> "TokenExchangeConfig":
        return cls(
            okta_domain=os.environ["OKTA_DOMAIN"],
            custom_authorization_server_id=os.environ["OKTA_CUSTOM_AS_ID"],
            requested_scope=os.environ["OKTA_SCOPE"],
            resource_audience=os.environ["OKTA_RESOURCE_AUDIENCE"],
            agent_client_id=os.environ["OKTA_AGENT_CLIENT_ID"],
            agent_key_id=os.environ["OKTA_AGENT_KEY_ID"],
            agent_private_key_jwk=json.loads(os.environ["OKTA_AGENT_PRIVATE_KEY_JWK"]),
        )

    def validate(self) -> None:
        if not self.okta_domain.startswith("https://"):
            raise ValueError("OKTA_DOMAIN must use https://")
        if not self.requested_scope or len(self.requested_scope.split()) != 1:
            raise ValueError("Request one least-privilege scope per exchange")
        if not self.resource_audience:
            raise ValueError("OKTA_RESOURCE_AUDIENCE is required")
        if self.agent_private_key_jwk.get("kid") != self.agent_key_id:
            raise ValueError("OKTA_AGENT_KEY_ID must match the private JWK kid")
        for field in ("kty", "n", "e", "d"):
            if not self.agent_private_key_jwk.get(field):
                raise ValueError(f"Agent private JWK is missing {field}")


class OktaTokenExchange:
    def __init__(
        self,
        config: TokenExchangeConfig,
        session: requests.Session | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.session = session or requests.Session()
        self._signing_key = RSAAlgorithm.from_jwk(
            json.dumps(config.agent_private_key_jwk)
        )

    def build_client_assertion(self, audience: str) -> str:
        """Sign a short-lived client assertion for one specific token endpoint."""
        now = int(time.time())
        return jwt.encode(
            {
                "iss": self.config.agent_client_id,
                "sub": self.config.agent_client_id,
                "aud": audience,
                "iat": now,
                "exp": now + 60,
                "jti": str(uuid.uuid4()),
            },
            self._signing_key,
            algorithm="RS256",
            headers={"kid": self.config.agent_key_id},
        )

    def id_jag_form(self, user_id_token: str) -> dict[str, str]:
        """Build Step 1 form data without logging the user's token."""
        return {
            "grant_type": TOKEN_EXCHANGE_GRANT,
            "client_assertion_type": CLIENT_ASSERTION_TYPE,
            "client_assertion": self.build_client_assertion(
                self.config.org_token_url
            ),
            "subject_token": user_id_token,
            "subject_token_type": ID_TOKEN_TYPE,
            "requested_token_type": ID_JAG_TYPE,
            "scope": self.config.requested_scope,
            "audience": self.config.custom_authorization_server_issuer,
        }

    def resource_token_form(self, id_jag: str) -> dict[str, str]:
        """Build Step 2 form data without logging the ID-JAG."""
        return {
            "grant_type": JWT_BEARER_GRANT,
            "client_assertion_type": CLIENT_ASSERTION_TYPE,
            "client_assertion": self.build_client_assertion(
                self.config.custom_authorization_server_token_url
            ),
            "assertion": id_jag,
        }

    def get_id_jag(self, user_id_token: str) -> str:
        response = self.session.post(
            self.config.org_token_url,
            data=self.id_jag_form(user_id_token),
            timeout=self.config.timeout_seconds,
        )
        self._raise_exchange_error(response, "ID-JAG exchange")
        return response.json()["access_token"]

    def get_access_token(self, id_jag: str) -> str:
        response = self.session.post(
            self.config.custom_authorization_server_token_url,
            data=self.resource_token_form(id_jag),
            timeout=self.config.timeout_seconds,
        )
        self._raise_exchange_error(response, "resource token exchange")
        return response.json()["access_token"]

    def exchange(self, user_id_token: str) -> str:
        """Run both steps and return the scoped resource access token."""
        return self.get_access_token(self.get_id_jag(user_id_token))

    def verify_access_token(self, access_token: str) -> dict[str, Any]:
        """Validate signature, issuer, audience, expiry, and required scope."""
        jwks_client = jwt.PyJWKClient(
            self.config.custom_authorization_server_keys_url
        )
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        claims = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self.config.custom_authorization_server_issuer,
            audience=self.config.resource_audience,
            options={"require": ["exp", "iss", "aud"]},
        )
        scopes = claims.get("scp", claims.get("scope", []))
        if isinstance(scopes, str):
            scopes = scopes.split()
        if self.config.requested_scope not in scopes:
            raise ValueError(
                f"Access token is missing {self.config.requested_scope}"
            )
        return claims

    @staticmethod
    def _raise_exchange_error(
        response: requests.Response,
        operation: str,
    ) -> None:
        if response.ok:
            return
        try:
            body = response.json()
            code = body.get("error", "exchange_failed")
            description = body.get("error_description", "Request was denied")
        except ValueError:
            code = "exchange_failed"
            description = "Okta returned a non-JSON error"
        raise RuntimeError(
            f"{operation} failed ({response.status_code}, {code}): {description}"
        )
