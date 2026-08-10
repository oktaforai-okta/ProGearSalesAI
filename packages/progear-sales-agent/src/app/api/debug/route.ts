import { NextResponse } from 'next/server';
import { API_BASE_URL, OKTA_DOMAIN, OKTA_CLIENT_ID, OKTA_ISSUER, APP_URL } from '@/lib/config';

/**
 * Returns a short, non-reversible prefix of a config value - enough to
 * sanity-check which environment a deployment is pointed at - without
 * echoing back the full client ID or URL from a debug endpoint.
 */
function safePrefix(value: string, length = 6): string | null {
  if (!value) return null;
  return value.length <= length ? value : `${value.slice(0, length)}...`;
}

export async function GET() {
  return NextResponse.json({
    // Configuration presence checks only - no raw client IDs, keys, or URLs.
    hasClientId: !!process.env.NEXT_PUBLIC_OKTA_CLIENT_ID,
    clientIdPrefix: safePrefix(process.env.NEXT_PUBLIC_OKTA_CLIENT_ID || ''),
    hasOidcPrivateKey: !!process.env.OKTA_OIDC_PRIVATE_KEY,
    hasIssuer: !!process.env.NEXT_PUBLIC_OKTA_ISSUER,
    hasNextAuthSecret: !!process.env.NEXTAUTH_SECRET,
    hasApiUrl: !!process.env.NEXT_PUBLIC_API_URL,
    // Resolved config: booleans and, at most, a safe prefix - never the
    // full client ID or a full URL.
    resolvedConfig: {
      hasApiBaseUrl: !!API_BASE_URL,
      hasOktaDomain: !!OKTA_DOMAIN,
      oktaClientIdPrefix: safePrefix(OKTA_CLIENT_ID),
      hasOktaIssuer: !!OKTA_ISSUER,
      hasAppUrl: !!APP_URL,
    },
  });
}
