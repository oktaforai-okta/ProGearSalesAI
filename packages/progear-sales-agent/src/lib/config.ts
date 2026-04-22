/**
 * Centralized configuration for environment variables
 * All environment-dependent values should be accessed from here
 */

// API Configuration
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Okta Configuration
export const OKTA_DOMAIN = process.env.NEXT_PUBLIC_OKTA_DOMAIN || '';
export const OKTA_CLIENT_ID = process.env.NEXT_PUBLIC_OKTA_CLIENT_ID || '';
export const OKTA_ISSUER = process.env.NEXT_PUBLIC_OKTA_ISSUER || '';

// MCP Server Configuration
export const MCP_SERVER_URL = process.env.MCP_SERVER_URL || 'http://localhost:3001';

// App Configuration
export const APP_URL = process.env.NEXTAUTH_URL || 'http://localhost:3000';
