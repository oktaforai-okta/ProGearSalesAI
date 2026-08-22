'use client';

import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Cloud,
  KeyRound,
  LockKeyhole,
  Route,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

export interface A2ATraceEvent {
  step: string;
  action: string;
  status: 'processing' | 'completed' | 'denied' | 'error';
  platform: string;
  agent: string;
  scope: string;
  correlation_id: string;
  detail?: string | null;
  act_chain?: string[];
}

interface Props {
  events?: A2ATraceEvent[];
  subject?: string | null;
  compact?: boolean;
  showInspectLink?: boolean;
}

const stepTarget: Record<string, { agent: string; platform: string; resource: string }> = {
  customer_context: {
    agent: 'Google Customer Agent',
    platform: 'Google ADK · Cloud Run',
    resource: 'Customer MCP',
  },
  inventory_write: {
    agent: 'AWS Inventory + Pricing Agent',
    platform: 'AWS Bedrock AgentCore',
    resource: 'Inventory MCP',
  },
  customer_notify: {
    agent: 'Google Customer Agent',
    platform: 'Google ADK · Cloud Run',
    resource: 'Customer MCP',
  },
};

function friendlySubject(subject?: string | null) {
  if (!subject) return 'Signed-in user';
  if (!subject.includes('@')) return subject;
  return subject
    .split('@')[0]
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function outcomeLabel(status: A2ATraceEvent['status']) {
  if (status === 'completed') return 'Granted & verified';
  if (status === 'denied') return 'Denied';
  if (status === 'processing') return 'In progress';
  return 'Failed closed';
}

function statusStyles(status: A2ATraceEvent['status']) {
  if (status === 'completed') return 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300';
  if (status === 'denied') return 'border-amber-400/25 bg-amber-400/10 text-amber-300';
  if (status === 'processing') return 'border-sky-400/25 bg-sky-400/10 text-sky-300';
  return 'border-rose-400/25 bg-rose-400/10 text-rose-300';
}

function safeCorrelationId(events: A2ATraceEvent[]) {
  const value = events.find((event) => event.correlation_id)?.correlation_id;
  return value || 'pending';
}

export function ChainOfCustody({ events, subject, compact = false, showInspectLink = false }: Props) {
  if (!events?.length) return null;

  const human = friendlySubject(subject);
  const specialistEvents = events.filter((event) => event.step !== 'route');
  const completedPlatforms = new Set(
    specialistEvents
      .filter((event) => event.status === 'completed')
      .map((event) => stepTarget[event.step]?.platform || event.platform),
  );

  return (
    <section className={`overflow-hidden rounded-2xl border border-white/10 bg-[#0b1018] text-white shadow-2xl shadow-black/20 ${compact ? 'mt-3' : ''}`}>
      <div className="border-b border-white/10 bg-gradient-to-r from-sky-400/[0.08] via-transparent to-violet-400/[0.08] px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-sky-200">
              <ShieldCheck className="h-4 w-4" />
              Chain of custody
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
              Retrospective delegation evidence across the ProGear, Google, and AWS agent runtimes.
            </p>
          </div>
          <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 font-mono text-[10px] text-slate-400">
            {safeCorrelationId(events)}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px]">
          <span className="rounded-lg border border-sky-400/20 bg-sky-400/10 px-2.5 py-1.5 font-medium text-sky-200">{human}</span>
          <ArrowRight className="h-3.5 w-3.5 text-slate-600" />
          <span className="rounded-lg border border-violet-400/20 bg-violet-400/10 px-2.5 py-1.5 font-medium text-violet-200">ProGear Coordinator</span>
          {specialistEvents.map((event, index) => {
            const target = stepTarget[event.step];
            return (
              <span className="contents" key={`${event.step}-${index}`}>
                <ArrowRight className="h-3.5 w-3.5 text-slate-600" />
                <span className="rounded-lg border border-white/10 bg-white/[0.05] px-2.5 py-1.5 text-slate-200">
                  {target?.agent || event.agent}
                </span>
              </span>
            );
          })}
        </div>
      </div>

      <div className={`grid gap-3 p-4 sm:p-5 ${compact ? '' : 'lg:grid-cols-2'}`}>
        <article className="rounded-xl border border-white/10 bg-white/[0.025] p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="rounded-lg bg-sky-400/10 p-2 text-sky-300"><Route className="h-4 w-4" /></div>
              <div>
                <p className="text-xs font-semibold">Session → Coordinator</p>
                <p className="mt-0.5 text-[10px] text-slate-500">Inbound delegated authority</p>
              </div>
            </div>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-emerald-300">
              Verified
            </span>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2 text-[10px]">
            <div><dt className="text-slate-600">Subject</dt><dd className="mt-0.5 text-slate-300">{human}</dd></div>
            <div><dt className="text-slate-600">Receiver</dt><dd className="mt-0.5 text-slate-300">ProGear Coordinator</dd></div>
            <div><dt className="text-slate-600">Requested scope</dt><dd className="mt-0.5 font-mono text-sky-300">agent.invoke</dd></div>
            <div><dt className="text-slate-600">Credential</dt><dd className="mt-0.5 text-slate-300">Short-lived access token</dd></div>
          </dl>
        </article>

        {specialistEvents.map((event, index) => {
          const target = stepTarget[event.step] || {
            agent: event.agent,
            platform: event.platform,
            resource: 'Protected resource',
          };
          const priorTarget = specialistEvents.slice(0, index).some((prior) => {
            const priorMeta = stepTarget[prior.step];
            return (priorMeta?.agent || prior.agent) === target.agent;
          });
          const StatusIcon = event.status === 'completed'
            ? CheckCircle2
            : event.status === 'denied'
              ? ShieldAlert
              : event.status === 'processing'
                ? Clock3
                : XCircle;

          return (
            <article key={`${event.step}-${index}`} className="rounded-xl border border-white/10 bg-white/[0.025] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="rounded-lg bg-violet-400/10 p-2 text-violet-300"><Cloud className="h-4 w-4" /></div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold">Coordinator → {target.agent}</p>
                    <p className="mt-0.5 truncate text-[10px] text-slate-500">{target.platform}</p>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[9px] font-semibold uppercase tracking-wider ${statusStyles(event.status)}`}>
                  <StatusIcon className="h-3 w-3" /> {outcomeLabel(event.status)}
                </span>
              </div>

              <div className="mt-3 rounded-lg border border-white/[0.07] bg-black/20 px-3 py-2.5">
                <div className="flex items-center justify-between gap-3 text-[10px]">
                  <span className="inline-flex items-center gap-1.5 text-slate-400"><KeyRound className="h-3 w-3 text-violet-300" />{priorTarget ? 'Scoped token reuse' : 'AI Token Exchange'}</span>
                  <span className="inline-flex items-center gap-1 text-emerald-300"><Clock3 className="h-3 w-3" />short-lived</span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 font-mono text-[9px]">
                  <span className="rounded bg-sky-400/10 px-1.5 py-1 text-sky-300">sub: {human}</span>
                  <span className="rounded bg-violet-400/10 px-1.5 py-1 text-violet-300">actor: ProGear Coordinator</span>
                  <span className="rounded bg-white/[0.05] px-1.5 py-1 text-slate-400">aud: {target.agent}</span>
                </div>
              </div>

              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[10px]">
                <div><dt className="text-slate-600">Delegation scope</dt><dd className="mt-0.5 font-mono text-sky-300">agent.invoke</dd></div>
                <div><dt className="text-slate-600">Resource scope</dt><dd className="mt-0.5 font-mono text-violet-300">{event.scope}</dd></div>
                <div><dt className="text-slate-600">Protected resource</dt><dd className="mt-0.5 text-slate-300">{target.resource} via Bridge</dd></div>
                <div><dt className="text-slate-600">Decision</dt><dd className="mt-0.5 text-slate-300">{outcomeLabel(event.status)}</dd></div>
              </dl>

              <p className="mt-3 text-[11px] leading-relaxed text-slate-400">{event.action}</p>
              {event.detail && <p className="mt-1.5 text-[10px] leading-relaxed text-slate-600">{event.detail}</p>}
            </article>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 bg-black/20 px-4 py-3 sm:px-5">
        <p className="inline-flex items-center gap-1.5 text-[10px] text-slate-500">
          <LockKeyhole className="h-3 w-3 text-emerald-300" />
          Raw JWTs, tenant identifiers, workload IDs, and signing material are intentionally withheld.
        </p>
        <div className="flex items-center gap-2">
          {completedPlatforms.size > 0 && (
            <span className="text-[9px] uppercase tracking-widest text-slate-600">{completedPlatforms.size} specialist platform{completedPlatforms.size === 1 ? '' : 's'}</span>
          )}
          {showInspectLink && (
            <Link href="/tokens" className="rounded-lg border border-sky-400/20 bg-sky-400/10 px-2.5 py-1.5 text-[10px] font-medium text-sky-200 hover:bg-sky-400/15">
              Inspect evidence →
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
