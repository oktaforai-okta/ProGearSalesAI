'use client';

import { useEffect, useState } from 'react';
import { ArrowRight, Bot, Database, Network, ShieldCheck } from 'lucide-react';
import { API_BASE_URL } from '@/lib/config';

interface RegistryAgent {
  key: string;
  name: string;
  platform: string;
  role: string;
  status: 'configured' | 'planned';
  dual_citizen: boolean;
  inbound: string[];
  outbound: string[];
}

interface RegistryResource {
  name: string;
  scopes: string[];
  expected_actor: string;
}

interface RegistrySnapshot {
  enabled: boolean;
  agents: RegistryAgent[];
  resources: RegistryResource[];
}

export function AgentRegistryPanel() {
  const [registry, setRegistry] = useState<RegistrySnapshot | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE_URL}/api/a2a/registry`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('registry unavailable')))
      .then((snapshot) => active && setRegistry(snapshot))
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  if (!registry) return null;

  return (
    <section className="mb-6 overflow-hidden rounded-2xl border border-primary/15 bg-white text-left shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-border bg-primary/[0.035] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-primary p-2 text-white"><Network className="h-4 w-4" /></div>
          <div>
            <h3 className="text-sm font-bold text-primary">Okta Agent Registry</h3>
            <p className="text-xs text-gray-500">Governed identities, inbound delegations, and resource connections</p>
          </div>
        </div>
        <span className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wide ${
          registry.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
        }`}>
          {registry.enabled ? 'Mesh enabled' : 'Design mode'}
        </span>
      </div>

      <div className="grid gap-3 p-4 lg:grid-cols-3">
        {registry.agents.map((agent) => (
          <article key={agent.key} className="rounded-xl border border-neutral-border bg-neutral-bg/60 p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <Bot className="h-4 w-4 flex-none text-accent" />
                <div className="min-w-0">
                  <h4 className="truncate text-xs font-bold text-primary">{agent.name}</h4>
                  <p className="truncate text-[10px] text-gray-500">{agent.platform}</p>
                </div>
              </div>
              <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                agent.status === 'configured'
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-slate-200 text-slate-600'
              }`}>
                {agent.status}
              </span>
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-gray-600">{agent.role}</p>
            <div className="mt-3 space-y-1.5 text-[10px] text-gray-500">
              <p className="flex gap-1.5"><ArrowRight className="h-3 w-3 flex-none rotate-180 text-sky-600" />{agent.inbound.join(', ')}</p>
              <p className="flex gap-1.5"><ArrowRight className="h-3 w-3 flex-none text-violet-600" />{agent.outbound.join(', ')}</p>
            </div>
            {agent.dual_citizen && (
              <div className="mt-3 flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wide text-okta-blue">
                <ShieldCheck className="h-3 w-3" /> Client + protected resource
              </div>
            )}
          </article>
        ))}
      </div>

      <div className="grid gap-3 border-t border-neutral-border bg-slate-50 px-4 py-3 md:grid-cols-2">
        {registry.resources.map((resource) => (
          <div key={resource.name} className="flex gap-3 rounded-lg bg-white p-3 ring-1 ring-slate-200">
            <Database className="mt-0.5 h-4 w-4 flex-none text-court-orange" />
            <div className="min-w-0">
              <p className="text-[11px] font-bold text-primary">{resource.name}</p>
              <p className="mt-0.5 text-[10px] text-gray-500">Immediate actor: {resource.expected_actor}</p>
              <p className="mt-1 font-mono text-[9px] text-okta-blue">{resource.scopes.join(' · ')}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
