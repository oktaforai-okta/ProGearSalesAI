'use client';

import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  CloudCog,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react';

function SignInContent() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams?.get('callbackUrl') || '/';
  const error = searchParams?.get('error');

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#080c12] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_5%,rgba(56,189,248,0.13),transparent_34%),radial-gradient(circle_at_88%_18%,rgba(139,92,246,0.12),transparent_30%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.035] [background-image:linear-gradient(rgba(255,255,255,.5)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.5)_1px,transparent_1px)] [background-size:44px_44px]" />

      <div className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-10 px-6 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:px-10">
        <section className="max-w-2xl">
          <div className="flex items-center gap-3">
            <span className="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-orange-400/20 bg-orange-400/10 text-xl">
              🏀
              <span className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-[#080c12] bg-emerald-400" />
            </span>
            <div>
              <p className="text-sm font-semibold text-white">CourtEdge ProGear</p>
              <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Governed sales operations</p>
            </div>
          </div>

          <div className="mt-14 inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/[0.08] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-300">
            <CloudCog className="h-3.5 w-3.5" /> Google ADK × AWS AgentCore
          </div>
          <h1 className="mt-5 text-4xl font-semibold leading-[1.08] tracking-[-0.04em] text-white sm:text-5xl">
            Cross-cloud agents,<br />accountable at every hop.
          </h1>
          <p className="mt-5 max-w-xl text-sm leading-7 text-slate-400">
            ProGear coordinates customer work in Google Cloud and inventory operations in AWS. Okta keeps the human at the root of authority and records the delegation trail end to end.
          </p>

          <div className="mt-9 grid max-w-xl gap-3 sm:grid-cols-3">
            {[
              [Fingerprint, 'Human subject', 'Sarah or Mike remains the root identity.'],
              [KeyRound, 'Scoped hops', 'Each agent receives target-bound authority.'],
              [LockKeyhole, 'Isolated tools', 'Bridge limits each agent to its MCP resource.'],
            ].map(([Icon, title, copy]) => {
              const FeatureIcon = Icon as typeof Fingerprint;
              return (
                <div key={String(title)} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                  <FeatureIcon className="h-4 w-4 text-sky-300" />
                  <p className="mt-3 text-[11px] font-medium text-slate-200">{String(title)}</p>
                  <p className="mt-1 text-[10px] leading-relaxed text-slate-500">{String(copy)}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="mx-auto w-full max-w-md rounded-3xl border border-white/10 bg-[#0b1018]/95 p-6 shadow-2xl shadow-black/30 backdrop-blur-xl sm:p-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-300">Secure workspace</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Sign in to ProGear</h2>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">Use the Sarah Sales or Mike Manager demo identity. The same request produces a policy-specific outcome.</p>
            </div>
            <span className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-2.5 text-emerald-300"><ShieldCheck className="h-5 w-5" /></span>
          </div>

          {error && (
            <div className="mt-6 rounded-xl border border-rose-400/20 bg-rose-400/[0.08] px-4 py-3 text-xs text-rose-200">
              Authentication could not be completed. Please start a new sign-in.
            </div>
          )}

          <button onClick={() => signIn('okta', { callbackUrl })} className="mt-7 flex w-full items-center justify-between rounded-xl bg-sky-400 px-4 py-3.5 text-sm font-semibold text-slate-950 shadow-lg shadow-sky-400/10 hover:bg-sky-300">
            <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4" />Continue with Okta</span>
            <ArrowRight className="h-4 w-4" />
          </button>

          <div className="mt-6 space-y-3 border-t border-white/10 pt-5">
            {[
              'Password-only authentication for the two demo personas',
              'Short-lived access is evaluated independently for each target',
              'No raw JWTs, private keys, or workload IDs are displayed',
            ].map((item) => (
              <p key={item} className="flex items-start gap-2 text-[10px] leading-relaxed text-slate-500"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 flex-none text-emerald-300" />{item}</p>
            ))}
          </div>

          <p className="mt-6 text-center text-[9px] uppercase tracking-[0.16em] text-slate-700">Secured by Okta for AI Agents</p>
        </section>
      </div>
    </main>
  );
}

export default function SignIn() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080c12]" />}>
      <SignInContent />
    </Suspense>
  );
}
