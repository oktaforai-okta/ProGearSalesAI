'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Code2, ShieldX } from 'lucide-react';

type ActorId = 'user' | 'agent' | 'idp' | 'resourceAs' | 'fga' | 'api';

interface Actor {
  id: ActorId;
  label: string;
  sublabel: string;
  color: string;
}

interface SequenceStep {
  from: ActorId;
  to: ActorId;
  label: string;
  shortLabel: string;
  plain: string;
  technical: string;
  blocked?: boolean;
}

interface SequenceDiagramProps {
  agentActive?: boolean;
  fgaEnabled?: boolean;
}

const BASE_ACTORS: Actor[] = [
  { id: 'user', label: 'Employee', sublabel: 'Sarah, Mike, or Joe', color: '#8b5cf6' },
  { id: 'agent', label: 'ProGear Agent', sublabel: 'Workload Principal', color: '#f97316' },
  { id: 'idp', label: 'Okta', sublabel: 'Identity provider', color: '#2563eb' },
  { id: 'resourceAs', label: 'Resource AS', sublabel: 'Local authorization', color: '#0f766e' },
  { id: 'api', label: 'Inventory API', sublabel: 'Protected resource', color: '#16a34a' },
];

const FGA_ACTOR: Actor = {
  id: 'fga',
  label: 'FGA',
  sublabel: 'Context decision',
  color: '#7c3aed',
};

function buildSteps(agentActive: boolean, fgaEnabled: boolean): SequenceStep[] {
  const firstSteps: SequenceStep[] = [
    {
      from: 'user',
      to: 'agent',
      label: 'Ask the agent to read or change inventory',
      shortLabel: 'User asks',
      plain: 'The employee asks one customer-owned agent to perform a business task.',
      technical: 'The signed-in employee remains the resource owner and the subject of the delegated request.',
    },
    {
      from: 'agent',
      to: 'idp',
      label: 'Authenticate the agent and present user context',
      shortLabel: 'Prove both identities',
      plain: 'The agent identifies itself and carries the signed-in employee’s identity to Okta.',
      technical: 'The Workload Principal authenticates as the OAuth client and presents the user’s subject token for exchange.',
    },
  ];

  if (!agentActive) {
    return [
      ...firstSteps,
      {
        from: 'idp',
        to: 'agent',
        label: 'Stop: the agent identity is deactivated',
        shortLabel: 'Exchange stopped',
        plain: 'Okta refuses to issue a new delegated grant, so the request never reaches Inventory.',
        technical: 'The new ID-JAG exchange fails. Any access token already issued remains subject to its own short expiry and revocation policy.',
        blocked: true,
      },
    ];
  }

  const steps: SequenceStep[] = [
    ...firstSteps,
    {
      from: 'idp',
      to: 'agent',
      label: 'Issue an ID-JAG for this user, client, and target',
      shortLabel: 'Issue ID-JAG',
      plain: 'Okta creates a short-lived, signed bridge between the employee, agent, and target authorization server.',
      technical: 'The ID-JAG identifies the end user in `sub`, the client acting for that user in `client_id`, and the Resource Authorization Server in `aud`.',
    },
    {
      from: 'agent',
      to: 'resourceAs',
      label: 'Exchange the ID-JAG for one scoped access token',
      shortLabel: 'Apply local policy',
      plain: 'The target authorization server makes its own decision and returns only the permission this task needs.',
      technical: 'The Resource Authorization Server validates issuer, audience, client continuity, user mapping, and local policy before issuing its access token.',
    },
  ];

  if (fgaEnabled) {
    steps.push({
      from: 'agent',
      to: 'fga',
      label: 'Evaluate role, quantity, and vacation context',
      shortLabel: 'Check live context',
      plain: 'The optional advanced layer decides whether to execute, request approval, or block the inventory write.',
      technical: 'FGA evaluates the live Okta claims plus action and quantity. It does not replace OAuth scope enforcement.',
    });
  }

  steps.push(
    {
      from: 'agent',
      to: 'api',
      label: 'Call Inventory with the scoped access token',
      shortLabel: 'Call the resource',
      plain: 'Only after the identity and authorization checks pass does the agent call the protected API.',
      technical: 'Inventory validates the bearer token’s signature, issuer, audience, expiry, and required scope before executing.',
    },
    {
      from: 'api',
      to: 'agent',
      label: 'Return the result and preserve the audit chain',
      shortLabel: 'Return + audit',
      plain: 'The employee receives the answer while the user, agent, resource, scope, and outcome remain traceable.',
      technical: 'Token-grant evidence in Okta and application/resource logs can be correlated without treating the agent as the user.',
    }
  );

  return steps;
}

export default function SequenceDiagram({ agentActive = true, fgaEnabled = false }: SequenceDiagramProps) {
  const actors = useMemo(
    () => (fgaEnabled ? [...BASE_ACTORS.slice(0, 4), FGA_ACTOR, BASE_ACTORS[4]] : BASE_ACTORS),
    [fgaEnabled]
  );
  const steps = useMemo(() => buildSteps(agentActive, fgaEnabled), [agentActive, fgaEnabled]);
  const [selectedStep, setSelectedStep] = useState(0);

  useEffect(() => setSelectedStep(0), [agentActive, fgaEnabled]);

  const current = steps[Math.min(selectedStep, steps.length - 1)];
  const viewWidth = 1120;
  const laneTop = 92;
  const rowHeight = 54;
  const diagramHeight = laneTop + steps.length * rowHeight + 42;
  const margin = 82;
  const laneX = (id: ActorId) => {
    const index = actors.findIndex((actor) => actor.id === id);
    return margin + ((viewWidth - margin * 2) * index) / Math.max(actors.length - 1, 1);
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
      <div className="border-b border-slate-200 px-5 py-5 dark:border-slate-800 sm:px-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-orange-600 dark:text-orange-400">Sequence diagram</p>
            <h2 className="mt-1 text-xl font-bold text-slate-950 dark:text-white">Follow one delegated request</h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
              Time moves down. Select a step for its plain-language meaning and protocol detail.
            </p>
          </div>
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${
            agentActive
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
              : 'bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300'
          }`}>
            {agentActive ? <CheckCircle2 className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
            {agentActive ? 'Agent active' : 'Agent deactivated'}
          </span>
        </div>

        <div className="mt-5 flex gap-2 overflow-x-auto pb-1" aria-label="Sequence steps">
          {steps.map((step, index) => (
            <button
              key={`${step.from}-${step.to}-${step.shortLabel}`}
              type="button"
              onClick={() => setSelectedStep(index)}
              aria-pressed={selectedStep === index}
              className={`flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs font-semibold transition ${
                selectedStep === index
                  ? step.blocked
                    ? 'border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950/50 dark:text-red-200'
                    : 'border-orange-300 bg-orange-50 text-orange-900 dark:border-orange-700 dark:bg-orange-950/40 dark:text-orange-100'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
              }`}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-current/10 text-[10px]">{index + 1}</span>
              {step.shortLabel}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto bg-slate-50/70 dark:bg-slate-900/40">
        <p className="px-5 pt-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 sm:hidden">Swipe to follow the sequence →</p>
        <svg
          viewBox={`0 0 ${viewWidth} ${diagramHeight}`}
          className="block min-w-[880px] w-full"
          role="img"
          aria-label="Sequence diagram showing the employee, governed AI agent, Okta, resource authorization server, optional FGA policy, and Inventory API"
        >
          <defs>
            <marker id="sequence-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
            </marker>
            <marker id="sequence-arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#f97316" />
            </marker>
            <marker id="sequence-arrow-blocked" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#dc2626" />
            </marker>
          </defs>

          {actors.map((actor) => {
            const x = laneX(actor.id);
            return (
              <g key={actor.id}>
                <rect x={x - 72} y={18} width={144} height={54} rx={12} className="fill-white stroke-slate-200 dark:fill-slate-950 dark:stroke-slate-700" strokeWidth={1.5} />
                <circle cx={x - 54} cy={36} r={5} fill={actor.color} />
                <text x={x} y={39} textAnchor="middle" className="fill-slate-900 text-[12px] font-bold dark:fill-white">{actor.label}</text>
                <text x={x} y={57} textAnchor="middle" className="fill-slate-500 text-[9px] dark:fill-slate-400">{actor.sublabel}</text>
                <line x1={x} y1={72} x2={x} y2={diagramHeight - 20} className="stroke-slate-300 dark:stroke-slate-700" strokeWidth={1.2} strokeDasharray="4 6" />
              </g>
            );
          })}

          {steps.map((step, index) => {
            const y = laneTop + index * rowHeight + 20;
            const active = selectedStep === index;
            const blocked = Boolean(step.blocked);
            const fromX = laneX(step.from);
            const toX = laneX(step.to);
            const direction = toX >= fromX ? 1 : -1;
            const startX = fromX + direction * 8;
            const endX = toX - direction * 10;
            const color = blocked ? '#dc2626' : active ? '#f97316' : '#64748b';
            const marker = blocked ? 'url(#sequence-arrow-blocked)' : active ? 'url(#sequence-arrow-active)' : 'url(#sequence-arrow)';
            return (
              <g
                key={`${step.from}-${step.to}-${index}`}
                onClick={() => setSelectedStep(index)}
                className="cursor-pointer"
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') setSelectedStep(index);
                }}
                aria-label={`Step ${index + 1}: ${step.label}`}
              >
                {active && <rect x={24} y={y - 23} width={viewWidth - 48} height={44} rx={10} fill={blocked ? '#fef2f2' : '#fff7ed'} opacity={0.9} />}
                <circle cx={34} cy={y} r={12} fill={color} />
                <text x={34} y={y + 4} textAnchor="middle" fill="white" className="text-[10px] font-bold">{index + 1}</text>
                <line
                  x1={startX}
                  y1={y}
                  x2={endX}
                  y2={y}
                  stroke={color}
                  strokeWidth={active ? 2.8 : 1.8}
                  strokeDasharray={blocked ? '7 5' : undefined}
                  markerEnd={marker}
                  opacity={active ? 1 : 0.72}
                />
                <rect
                  x={(fromX + toX) / 2 - Math.min(190, Math.max(94, step.label.length * 3.1))}
                  y={y - 18}
                  width={Math.min(380, Math.max(188, step.label.length * 6.2))}
                  height={20}
                  rx={10}
                  className="fill-slate-50 dark:fill-slate-900"
                />
                <text x={(fromX + toX) / 2} y={y - 5} textAnchor="middle" fill={color} className="text-[10px] font-semibold">
                  {step.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="grid gap-4 border-t border-slate-200 p-5 dark:border-slate-800 sm:grid-cols-2 sm:p-7">
        <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <ArrowRight className="h-4 w-4" /> Plain language
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-800 dark:text-slate-200">{current.plain}</p>
        </div>
        <div className="rounded-xl bg-blue-50/70 p-4 dark:bg-blue-950/30">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-blue-700 dark:text-blue-300">
            <Code2 className="h-4 w-4" /> Protocol detail
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-800 dark:text-slate-200">{current.technical}</p>
        </div>
      </div>
    </section>
  );
}
