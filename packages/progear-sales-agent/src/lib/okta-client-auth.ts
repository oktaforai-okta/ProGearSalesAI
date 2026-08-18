import { importJWK, SignJWT, type JWK } from 'jose';

const CLIENT_ASSERTION_TYPE =
  'urn:ietf:params:oauth:client-assertion-type:jwt-bearer';

function getClientId(): string {
  const clientId = process.env.NEXT_PUBLIC_OKTA_CLIENT_ID;
  if (!clientId) {
    throw new Error('NEXT_PUBLIC_OKTA_CLIENT_ID is not configured');
  }
  return clientId;
}

function getPrivateJwk(): JWK {
  const value = process.env.OKTA_OIDC_PRIVATE_KEY;
  if (!value) {
    throw new Error('OKTA_OIDC_PRIVATE_KEY is not configured');
  }

  let jwk: JWK;
  try {
    jwk = JSON.parse(value) as JWK;
  } catch {
    throw new Error('OKTA_OIDC_PRIVATE_KEY must contain valid JSON');
  }
  if (!jwk.kid || !jwk.d) {
    throw new Error('OKTA_OIDC_PRIVATE_KEY must be a private JWK with kid and d');
  }
  return jwk;
}

export function getOktaTokenEndpoint(): string {
  const issuer = (process.env.A2A_USER_ISSUER || process.env.NEXT_PUBLIC_OKTA_ISSUER)?.replace(/\/$/, '');
  if (!issuer) {
    throw new Error('A2A_USER_ISSUER or NEXT_PUBLIC_OKTA_ISSUER is not configured');
  }
  return /\/oauth2\/[^/]+$/.test(issuer)
    ? `${issuer}/v1/token`
    : `${issuer}/oauth2/v1/token`;
}

export function getPrivateJwks(): { keys: Array<Record<string, unknown>> } {
  return { keys: [getPrivateJwk() as unknown as Record<string, unknown>] };
}

export async function createClientAssertion(
  audience = getOktaTokenEndpoint()
): Promise<string> {
  const clientId = getClientId();
  const jwk = getPrivateJwk();
  const key = await importJWK(jwk, 'RS256');

  return new SignJWT({})
    .setProtectedHeader({ alg: 'RS256', kid: jwk.kid })
    .setIssuer(clientId)
    .setSubject(clientId)
    .setAudience(audience)
    .setIssuedAt()
    .setExpirationTime('60s')
    .setJti(crypto.randomUUID())
    .sign(key);
}

export async function getPrivateKeyJwtParameters(
  audience = getOktaTokenEndpoint()
): Promise<Record<string, string>> {
  return {
    client_id: getClientId(),
    client_assertion_type: CLIENT_ASSERTION_TYPE,
    client_assertion: await createClientAssertion(audience),
  };
}
