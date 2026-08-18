import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from a2a.models import A2AAccessDenied
from a2a.registry import registry_snapshot
from a2a.user_token import A2AUserTokenVerifier


class _SigningKey:
    def __init__(self, key):
        self.key = key


class _StaticJwks:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token):
        return _SigningKey(self.public_key)


class A2AUserTokenVerifierTests(unittest.TestCase):
    issuer = "https://example.okta.com/oauth2/aus-test"
    audience = "https://agents.progear.example/coordinator"

    def setUp(self):
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.verifier = A2AUserTokenVerifier(
            issuer=self.issuer,
            audience=self.audience,
            jwks_client=_StaticJwks(self.private_key.public_key()),
        )

    def token(self, **overrides):
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": "00u-mike",
            "iat": now,
            "exp": now + 300,
            "scp": ["agent.invoke", "inventory:write", "customer:notify"],
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test"})

    def test_accepts_a_signed_coordinator_bound_token(self):
        claims = self.verifier.verify(self.token())
        self.assertEqual(claims["sub"], "00u-mike")

    def test_rejects_a_token_for_a_sibling_resource(self):
        with self.assertRaises(A2AAccessDenied):
            self.verifier.verify(self.token(aud="https://agents.progear.example/aws"))

    def test_rejects_a_token_without_agent_invoke_scope(self):
        with self.assertRaises(A2AAccessDenied):
            self.verifier.verify(self.token(scp=["inventory:write"]))


class RegistrySnapshotTests(unittest.TestCase):
    def test_never_returns_workload_principal_ids(self):
        snapshot = registry_snapshot({
            "PROGEAR_A2A_ENABLED": "true",
            "A2A_COORDINATOR_AGENT_ID": "wlp-coordinator-secret-ish-id",
        })
        rendered = str(snapshot)
        self.assertNotIn("wlp-coordinator-secret-ish-id", rendered)
        self.assertEqual(snapshot["agents"][0]["status"], "configured")
        self.assertEqual(snapshot["agents"][1]["status"], "planned")


if __name__ == "__main__":
    unittest.main()
