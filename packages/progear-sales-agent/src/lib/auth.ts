import type { NextAuthOptions } from 'next-auth';
import type { JWT } from 'next-auth/jwt';
import { createRemoteJWKSet, jwtVerify } from 'jose';
import OktaProvider from 'next-auth/providers/okta';
import {
  getOktaTokenEndpoint,
  getPrivateJwks,
  getPrivateKeyJwtParameters,
} from '@/lib/okta-client-auth';

// The Okta AI SDK's Step 1 (ID token -> ID-JAG at the Org AS) needs a live,
// unexpired ID token. Okta ID tokens are typically short-lived (~1hr), and
// without this refresh the ID token captured at login goes stale for any
// session left open longer than that - every chat message after expiry then
// fails Step 1 with 'subject_token' is invalid, which orchestrator.py now
// surfaces as an explicit "session expired" error instead of silently
// swallowing it. This refresh removes the need for that error path entirely
// for normal-length sessions.
//
// Requires the Okta OIDC app to have the refresh_token grant type enabled and
// the authorization request to include the offline_access scope - see the
// `authorization.params.scope` below and the deployment note in the repo.
function getOktaIssuer(): string {
  return process.env.NEXT_PUBLIC_OKTA_ISSUER!.replace(/\/$/, '');
}

function getOktaIdTokenJwksUri(): URL {
  const issuer = getOktaIssuer();
  const clientId = process.env.NEXT_PUBLIC_OKTA_CLIENT_ID!;

  // Okta Org AS ID tokens use app-specific signing keys. The standard
  // discovery document advertises the org-wide JWKS URL, so include the
  // client_id query parameter to retrieve the key set that signed this app's
  // ID token. Access-token validation still uses the normal issuer JWKS.
  return new URL(`${issuer}/oauth2/v1/keys?client_id=${encodeURIComponent(clientId)}`);
}

async function verifyOktaIdToken(idToken: string): Promise<void> {
  const issuer = getOktaIssuer();
  const clientId = process.env.NEXT_PUBLIC_OKTA_CLIENT_ID!;
  const keySet = createRemoteJWKSet(getOktaIdTokenJwksUri());

  await jwtVerify(idToken, keySet, {
    issuer,
    audience: clientId,
    algorithms: ['RS256'],
  });
}

async function refreshOktaToken(token: JWT): Promise<JWT> {
  try {
    const tokenEndpoint = getOktaTokenEndpoint();
    const clientAuthentication = await getPrivateKeyJwtParameters(tokenEndpoint);
    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: token.refreshToken || '',
        ...clientAuthentication,
      }),
    });

    const refreshed = await response.json();
    if (!response.ok) throw refreshed;
    if (!refreshed.id_token) {
      throw new Error('Okta refresh response did not contain an ID token');
    }
    await verifyOktaIdToken(refreshed.id_token);

    return {
      ...token,
      idToken: refreshed.id_token,
      accessToken: refreshed.access_token,
      expiresAt: Math.floor(Date.now() / 1000) + refreshed.expires_in,
      refreshToken: refreshed.refresh_token ?? token.refreshToken,
      error: undefined,
    };
  } catch (error) {
    console.error('Error refreshing Okta token', error);
    // Keep the stale token rather than dropping the session - the next
    // /api/chat call will surface a clear "session expired" error via the
    // token_expired path in multi_agent_auth.py, and the sign-in page is one
    // click away.
    return { ...token, error: 'RefreshAccessTokenError' };
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    {
      ...OktaProvider({
      clientId: process.env.NEXT_PUBLIC_OKTA_CLIENT_ID!,
      // NextAuth v4 requires this property in its provider type, but
      // private_key_jwt authentication never sends or uses this value.
      clientSecret: 'unused-private-key-jwt',
      issuer: process.env.NEXT_PUBLIC_OKTA_ISSUER!,
      client: {
        token_endpoint_auth_method: 'private_key_jwt',
        token_endpoint_auth_signing_alg: 'RS256',
      },
      jwks: getPrivateJwks(),
      token: {
        async request({ client, params, checks, provider }) {
          const tokens = await client.callback(
            provider.callbackUrl,
            params,
            checks,
            {
              clientAssertionPayload: {
                aud: getOktaTokenEndpoint(),
              },
            }
          );
          return { tokens };
        },
      },
      authorization: { params: { scope: 'openid profile email offline_access' } },
      }),
      // NextAuth's built-in Okta provider reads the discovery document's
      // org-wide JWKS URL. Okta Org AS ID tokens are signed with an
      // app-specific key, available only from the client_id-qualified JWKS
      // endpoint, so verify that signature explicitly in the jwt callback.
      idToken: false,
    },
  ],
  pages: {
    signIn: '/auth/signin',
  },
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        if (!account.id_token) {
          throw new Error('Okta did not return an ID token');
        }
        await verifyOktaIdToken(account.id_token);

        token.accessToken = account.access_token;
        token.idToken = account.id_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
        return token;
      }

      // Refresh ~60s before actual expiry to avoid a request racing the
      // exact expiry boundary.
      if (token.expiresAt && Date.now() < token.expiresAt * 1000 - 60_000) {
        return token;
      }
      if (!token.refreshToken) {
        return token;
      }
      return refreshOktaToken(token);
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.idToken = token.idToken as string;
      session.error = token.error;
      session.user = {
        ...session.user,
        id: token.sub as string,
      };
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  debug: true,
};
