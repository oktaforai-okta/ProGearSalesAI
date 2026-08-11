'use client';

import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { ThemeSelector } from '@/components/ThemeProvider';

function SignInContent() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams?.get('callbackUrl') || '/';
  const error = searchParams?.get('error');

  const handleSignIn = () => {
    signIn('okta', { callbackUrl });
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-slate-100 via-orange-50 to-amber-100 px-4 py-20 dark:from-primary dark:via-primary-light dark:to-court-brown sm:py-12">
      <div className="absolute right-4 top-4 z-20">
        <ThemeSelector />
      </div>
      {/* Basketball Court Pattern Background */}
      <div className="absolute inset-0 opacity-5">
        <svg className="w-full h-full" viewBox="0 0 400 400" preserveAspectRatio="xMidYMid slice">
          <rect fill="none" stroke="#ff6b35" strokeWidth="4" x="20" y="20" width="360" height="360" rx="10"/>
          <circle cx="200" cy="200" r="60" fill="none" stroke="#ff6b35" strokeWidth="3"/>
          <line x1="200" y1="20" x2="200" y2="380" stroke="#ff6b35" strokeWidth="3"/>
          <path d="M20 200 Q100 150 200 200 Q300 250 380 200" fill="none" stroke="#ff6b35" strokeWidth="2"/>
        </svg>
      </div>

      {/* Animated Basketball Elements */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-10 left-10 opacity-20 animate-bounce text-8xl" style={{ animationDuration: '3s' }}>
          🏀
        </div>
        <div className="absolute bottom-20 right-10 opacity-15 animate-bounce text-9xl" style={{ animationDuration: '4s', animationDelay: '1s' }}>
          🏀
        </div>
        <div className="absolute top-1/3 right-1/4 opacity-10 animate-pulse text-6xl">
          🏀
        </div>
      </div>

      {/* Glowing accent orbs */}
      <div className="absolute top-20 left-20 w-64 h-64 bg-accent rounded-full blur-3xl opacity-20 animate-pulse"></div>
      <div className="absolute bottom-20 right-20 w-96 h-96 bg-court-orange rounded-full blur-3xl opacity-15 animate-pulse" style={{ animationDelay: '1s' }}></div>

      <div className="relative z-10 w-full max-w-sm rounded-2xl border-2 border-accent/30 bg-gradient-to-br from-white/95 to-white/90 p-6 shadow-2xl backdrop-blur-sm dark:from-slate-900/95 dark:to-slate-950/90 sm:p-8">
        {/* Basketball Logo */}
        <div className="mb-6 text-center">
          <div className="relative mb-3 inline-flex items-center justify-center">
            <div className="absolute inset-0 bg-accent/20 rounded-full blur-xl animate-pulse"></div>
            <span className="relative z-10 text-6xl">🏀</span>
          </div>
          <h1 className="mb-2 bg-gradient-to-r from-primary via-court-orange to-accent bg-clip-text text-3xl font-bold text-transparent">
            CourtEdge ProGear
          </h1>
          <p className="font-display text-base text-gray-600 dark:text-slate-300">
            Basketball Equipment Sales Intelligence
          </p>
        </div>

        {/* Security Badge - Basketball styled */}
        <div className="mb-5 rounded-xl border border-okta-blue/30 bg-gradient-to-r from-okta-blue/10 via-primary/5 to-accent/10 p-3">
          <div className="flex items-center justify-center space-x-3">
            <svg className="w-6 h-6 text-okta-blue" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="font-bold text-gray-700 dark:text-slate-100">Enterprise Secured</span>
            <div className="w-2 h-2 bg-success-green rounded-full animate-pulse"></div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-hoop-red/10 border-l-4 border-hoop-red rounded-lg">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-hoop-red mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <p className="text-sm text-hoop-red font-medium">
                {error === 'OAuthCallback'
                  ? 'Authentication failed. Please try again.'
                  : 'An error occurred. Please try again.'}
              </p>
            </div>
          </div>
        )}

        {/* Sign In Button - Basketball Orange Theme */}
        <button
          onClick={handleSignIn}
          className="flex w-full items-center justify-center space-x-3 rounded-xl border-b-4 border-court-brown/50 bg-gradient-to-r from-accent to-court-orange px-6 py-3 font-bold text-white shadow-lg transition-all duration-300 ease-in-out hover:scale-[1.02] hover:from-court-orange hover:to-accent hover:shadow-xl"
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2"/>
            <path d="M12 2v20M2 12h20" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
          <span>Sign in with Okta</span>
        </button>
      </div>
    </div>
  );
}

export default function SignIn() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary via-primary-light to-court-brown">
        <div className="flex flex-col items-center space-y-4">
          <span className="text-6xl animate-bounce">🏀</span>
          <div className="text-white text-xl font-display">Loading CourtEdge ProGear...</div>
        </div>
      </div>
    }>
      <SignInContent />
    </Suspense>
  );
}
