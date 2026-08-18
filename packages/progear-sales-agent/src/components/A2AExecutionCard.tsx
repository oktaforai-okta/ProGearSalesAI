'use client';

import { CheckCircle2, Cloud, ShieldAlert, XCircle } from 'lucide-react';

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

export function A2AExecutionCard({ events }: { events?: A2ATraceEvent[] }) {
  if (!events?.length) return null;
  const correlationId = events[0]?.correlation_id;

  return (
    <section className="mt-3 overflow-hidden rounded-xl border border-okta-blue/20 bg-slate-950 text-white shadow-lg">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2">
          <Cloud className="h-4 w-4 text-sky-300" />
          <span className="text-xs font-semibold tracking-wide">Cross-platform agent execution</span>
        </div>
        <code className="text-[10px] text-slate-400">{correlationId}</code>
      </div>
      <div className="divide-y divide-white/10">
        {events.map((event, index) => {
          const StatusIcon = event.status === 'completed'
            ? CheckCircle2
            : event.status === 'denied'
              ? ShieldAlert
              : XCircle;
          const statusColor = event.status === 'completed'
            ? 'text-emerald-300'
            : event.status === 'denied'
              ? 'text-amber-300'
              : 'text-rose-300';
          return (
            <div key={`${event.step}-${index}`} className="flex gap-3 px-4 py-3">
              <StatusIcon className={`mt-0.5 h-4 w-4 flex-none ${statusColor}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-xs font-semibold text-white">{event.agent}</span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-slate-300">
                    {event.platform}
                  </span>
                  <code className="text-[10px] text-sky-300">{event.scope}</code>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-slate-300">{event.action}</p>
                {event.detail && <p className="mt-1 text-[10px] text-slate-400">{event.detail}</p>}
                {!!event.act_chain?.length && (
                  <p className="mt-1 truncate font-mono text-[10px] text-violet-300">
                    act: {event.act_chain.join(' ← ')}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
