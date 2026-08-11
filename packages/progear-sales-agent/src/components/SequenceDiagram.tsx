'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ShieldX } from 'lucide-react';

type ActorId = 'user' | 'agent' | 'okta' | 'resourceAs' | 'fga' | 'api';

interface Actor {
  id: ActorId;
  label: string;
  sublabel: string;
  color: string;
}

interface Step {
  from: ActorId;
  to: ActorId;
  label: string;
  detail: string;
  blocked?: boolean;
}

interface SequenceDiagramProps {
  agentActive?: boolean;
  fgaEnabled?: boolean;
}

const BASE_ACTORS: Actor[] = [
  { id: 'user', label: 'Employee', sublabel: 'subject', color: '#8b5cf6' },
  { id: 'agent', label: 'ProGear Agent', sublabel: 'Workload Principal', color: '#f97316' },
  { id: 'okta', label: 'Okta', sublabel: 'Identity Provider', color: '#3b82f6' },
  { id: 'resourceAs', label: 'Resource AS', sublabel: 'local policy', color: '#0f766e' },
  { id: 'api', label: 'Inventory API', sublabel: 'protected resource', color: '#4d9f45' },
];

const FGA_ACTOR: Actor = { id: 'fga', label: 'FGA', sublabel: 'context decision', color: '#7c3aed' };

function buildSteps(agentActive: boolean, fgaEnabled: boolean): Step[] {
  const opening: Step[] = [
    {
      from: 'user', to: 'agent', label: 'Inventory request',
      detail: 'The signed-in employee asks the customer-owned agent to read or change inventory.',
    },
    {
      from: 'agent', to: 'okta', label: 'ID token + client assertion',
      detail: 'The Workload Principal authenticates and presents the employee identity for exchange.',
    },
  ];

  if (!agentActive) {
    return [
      ...opening,
      {
        from: 'okta', to: 'agent', label: 'Rejected — agent inactive',
        detail: 'No new ID-JAG or resource access token is issued.', blocked: true,
      },
    ];
  }

  const steps: Step[] = [
    ...opening,
    {
      from: 'okta', to: 'agent', label: 'ID-JAG',
      detail: 'Signed grant: sub=user · client_id=agent · aud=Resource AS.',
    },
    {
      from: 'agent', to: 'resourceAs', label: 'ID-JAG + scope',
      detail: 'The Resource AS validates the grant and applies its local policy.',
    },
    {
      from: 'resourceAs', to: 'agent', label: 'Scoped access token',
      detail: 'A short-lived inventory:read or inventory:write token is returned.',
    },
  ];

  if (fgaEnabled) {
    steps.push(
      {
        from: 'agent', to: 'fga', label: 'Role + quantity + vacation',
        detail: 'FGA evaluates the live inventory context.',
      },
      {
        from: 'fga', to: 'agent', label: 'Allow · OIG approval · block',
        detail: 'The inventory action executes, waits for a Manager/VP, or stops.',
      }
    );
  }

  steps.push(
    {
      from: 'agent', to: 'api', label: 'Bearer token',
      detail: 'Inventory validates the token before executing the authorized action.',
    },
    {
      from: 'api', to: 'agent', label: 'Result + audit',
      detail: 'The response returns with user, agent, resource, scope, and outcome traceable.',
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

  const currentIndex = Math.min(selectedStep, steps.length - 1);
  const current = steps[currentIndex];
  const viewWidth = 1160;
  const margin = 82;
  const laneTop = 88;
  const rowHeight = 48;
  const diagramHeight = laneTop + steps.length * rowHeight + 36;
  const laneX = (id: ActorId) => {
    const index = actors.findIndex((actor) => actor.id === id);
    return margin + ((viewWidth - margin * 2) * index) / Math.max(actors.length - 1, 1);
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-[#0b0f1a]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800 sm:px-6">
        <div>
          <h2 className="font-bold text-slate-950 dark:text-white">Request sequence</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Time moves down · click a step for detail</p>
        </div>
        <div className="flex items-center gap-2">
          {fgaEnabled ? <span className="rounded-full bg-violet-100 px-2.5 py-1 text-[10px] font-bold text-violet-800 dark:bg-violet-950 dark:text-violet-200">FGA</span> : null}
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold ${
            agentActive
              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200'
              : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200'
          }`}>
            {agentActive ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
            {agentActive ? 'ACTIVE' : 'DEACTIVATED'}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto bg-slate-50/70 dark:bg-[#0d111c]">
        <p className="px-5 pt-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 sm:hidden">Swipe to follow the sequence →</p>
        <svg
          viewBox={`0 0 ${viewWidth} ${diagramHeight}`}
          className="block min-w-[900px] w-full"
          role="img"
          aria-label="Sequence diagram for the ProGear agent token exchange and optional FGA inventory decision"
        >
          <defs>
            <marker id="seq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0 0 L10 5 L0 10 Z" fill="#94a3b8" />
            </marker>
            <marker id="seq-arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0 0 L10 5 L0 10 Z" fill="#f97316" />
            </marker>
            <marker id="seq-arrow-blocked" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0 0 L10 5 L0 10 Z" fill="#dc2626" />
            </marker>
          </defs>

          {actors.map((actor) => {
            const x = laneX(actor.id);
            return (
              <g key={actor.id}>
                <rect x={x - 72} y={14} width={144} height={52} rx={11} className="fill-white stroke-slate-300 dark:fill-[#111827] dark:stroke-slate-600" strokeWidth={1.7} />
                <circle cx={x - 54} cy={32} r={5} fill={actor.color} />
                <text x={x} y={35} textAnchor="middle" className="fill-slate-950 text-[12px] font-bold dark:fill-white">{actor.label}</text>
                <text x={x} y={52} textAnchor="middle" className="fill-slate-500 text-[9px] dark:fill-slate-400">{actor.sublabel}</text>
                <line x1={x} y1={66} x2={x} y2={diagramHeight - 18} className="stroke-slate-300 dark:stroke-slate-700" strokeWidth={1.5} strokeDasharray="4 6" />
              </g>
            );
          })}

          {steps.map((step, index) => {
            const selected = currentIndex === index;
            const blocked = Boolean(step.blocked);
            const fromX = laneX(step.from);
            const toX = laneX(step.to);
            const direction = toX >= fromX ? 1 : -1;
            const y = laneTop + index * rowHeight + 18;
            const labelWidth = Math.min(210, Math.max(84, step.label.length * 6.2 + 20));
            return (
              <g
                key={`${step.from}-${step.to}-${index}`}
                className="cursor-pointer outline-none"
                role="button"
                tabIndex={0}
                aria-label={`Step ${index + 1}: ${step.label}`}
                onClick={() => setSelectedStep(index)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') setSelectedStep(index);
                }}
              >
                {selected ? (
                  <rect x={25} y={y - 20} width={viewWidth - 50} height={40} rx={10} className={blocked ? 'fill-red-50 dark:fill-red-950/35' : 'fill-orange-50 dark:fill-orange-950/25'} />
                ) : null}
                <circle cx={34} cy={y} r={12} fill={blocked ? '#dc2626' : selected ? '#f97316' : '#64748b'} />
                <text x={34} y={y + 4} textAnchor="middle" fill="white" className="text-[10px] font-bold">{index + 1}</text>
                <line
                  x1={fromX + direction * 10}
                  y1={y}
                  x2={toX - direction * 12}
                  y2={y}
                  className={blocked ? 'stroke-red-600' : selected ? 'stroke-orange-500' : 'stroke-slate-600 dark:stroke-slate-300'}
                  strokeWidth={blocked || selected ? 3.5 : 2.7}
                  strokeDasharray={blocked ? '8 6' : undefined}
                  strokeLinecap="round"
                  markerEnd={blocked ? 'url(#seq-arrow-blocked)' : selected ? 'url(#seq-arrow-active)' : 'url(#seq-arrow)'}
                />
                <rect
                  x={(fromX + toX) / 2 - labelWidth / 2}
                  y={y - 12}
                  width={labelWidth}
                  height={23}
                  rx={11.5}
                  className="fill-white stroke-slate-200 dark:fill-[#0d111c] dark:stroke-slate-700"
                />
                <text
                  x={(fromX + toX) / 2}
                  y={y + 4}
                  textAnchor="middle"
                  className={blocked ? 'fill-red-600 text-[10px] font-bold' : selected ? 'fill-orange-600 text-[10px] font-bold dark:fill-orange-400' : 'fill-slate-700 text-[10px] font-semibold dark:fill-slate-200'}
                >
                  {step.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-200 px-5 py-3 text-sm dark:border-slate-800 sm:px-6">
        <span className="font-mono text-xs font-bold text-orange-600 dark:text-orange-400">{String(currentIndex + 1).padStart(2, '0')}</span>
        <span className="font-bold text-slate-950 dark:text-white">{current.label}</span>
        <span className="hidden text-slate-300 dark:text-slate-700 sm:inline">|</span>
        <span className="text-slate-600 dark:text-slate-300">{current.detail}</span>
      </div>
    </section>
  );
}
