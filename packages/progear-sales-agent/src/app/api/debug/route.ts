import { NextResponse } from 'next/server';
import { API_BASE_URL, OKTA_DOMAIN, OKTA_CLIENT_ID, OKTA_ISSUER, APP_URL } from '@/lib/config';

export async function GET() {
  return NextResponse.json({
    // Raw environment variable checks
    hasClientId: !!process.env.NEXT_PUBLIC_OKTA_CLIENT_ID,
    clientIdLength: process.env.NEXT_PUBLIC_OKTA_CLIENT_ID?.length || 0,
    hasClientSecret: !!process.env.OKTA_CLIENT_SECRET,
    clientSecretLength: process.env.OKTA_CLIENT_SECRET?.length || 0,
    hasIssuer: !!process.env.NEXT_PUBLIC_OKTA_ISSUER,
    hasNextAuthSecret: !!process.env.NEXTAUTH_SECRET,
    hasApiUrl: !!process.env.NEXT_PUBLIC_API_URL,
    // Resolved config values (what the app actually uses)
    resolvedConfig: {
      apiBaseUrl: API_BASE_URL,
      oktaDomain: OKTA_DOMAIN,
      oktaClientId: OKTA_CLIENT_ID,
      oktaIssuer: OKTA_ISSUER,
      appUrl: APP_URL,
    },
  });
}
