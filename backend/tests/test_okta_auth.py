import os
import unittest
from unittest.mock import patch

from auth.okta_auth import OktaAuth


class OktaAuthConfigurationTests(unittest.TestCase):
    def test_org_issuer_uses_client_qualified_id_token_keys(self):
        with patch.dict(
            os.environ,
            {
                "OKTA_ISSUER": "https://example.okta.com",
                "OKTA_CLIENT_ID": "wlp-agent",
            },
            clear=True,
        ):
            auth = OktaAuth()
        self.assertEqual(
            auth.jwks_uri,
            "https://example.okta.com/oauth2/v1/keys?client_id=wlp-agent",
        )

    def test_custom_issuer_uses_issuer_keys(self):
        with patch.dict(
            os.environ,
            {
                "OKTA_ISSUER": "https://example.okta.com/oauth2/custom",
                "OKTA_CLIENT_ID": "web-client",
            },
            clear=True,
        ):
            auth = OktaAuth()
        self.assertEqual(
            auth.jwks_uri,
            "https://example.okta.com/oauth2/custom/v1/keys",
        )


if __name__ == "__main__":
    unittest.main()
