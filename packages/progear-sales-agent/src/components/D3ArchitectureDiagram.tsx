'use client';

import { useMemo, useState } from 'react';
import { curveBumpX, line } from 'd3-shape';
import {
  Activity,
  ArrowRight,
  BookOpen,
  Braces,
  CheckCircle2,
  CircleStop,
  Fingerprint,
  Power,
  ShieldX,
  Sparkles,
} from 'lucide-react';
import { useFGASimulation } from '@/hooks/useFGASimulation';
import SequenceDiagram from './SequenceDiagram';

type NodeId = 'user' | 'agent' | 'idjag' | 'resourceAs' | 'fga' | 'api';

interface ArchitectureNode {
  id: NodeId;
  step: string;
  label: string;
  sublabel: string;
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  plain: string;
  technical: string;
}

interface ArchitectureEdge {
  from: NodeId;
  to: NodeId;
  label: string;
  blocked?: boolean;
  dimmed?: boolean;
}

const VIEW_WIDTH = 1280;
const VIEW_HEIGHT = 340;

function connectorPath(from: ArchitectureNode, to: ArchitectureNode): string {
  const draw = line<[number, number]>().curve(curveBumpX);
  return draw([
    [from.x + from.w, from.y + from.h / 2],
    [to.x, to.y + to.h / 2],
  ]) ?? '';
}

function nodeData(fgaEnabled: boolean): ArchitectureNode[] {
  const common: ArchitectureNode[] = [
    {
      id: 'user', step: '1', label: 'Employee', sublabel: 'The subject',
      x: 24, y: 112, w: 164, h: 104, color: '#8b5cf6',
      plain: 'Sarah, Mike, or Joe signs in and asks the agent to perform a task.',
      technical: 'The employee remains the resource owner identified by the ID-JAG subject (`sub`).',
    },
    {
      id: 'agent', step: '2', label: 'ProGear Agent', sublabel: 'Workload Principal',
      x: 232, y: 96, w: 194, h: 136, color: '#f97316',
      plain: 'The agent has a governed identity of its own. It never disappears inside the user’s identity.',
      technical: 'Okta manages the `wlp...` identity, owners, public credentials, lifecycle, and resource connections.',
    },
    {
      id: 'idjag', step: '3', label: 'Okta ID-JAG', sublabel: 'Identity bridge',
      x: 474, y: 112, w: 180, h: 104, color: '#2563eb',
      plain: 'Okta creates signed proof tying this user, this client, and this target together.',
      technical: 'The ID-JAG carries `sub` (end user), `client_id` (client acting for the user), and `aud` (Resource Authorization Server).',
    },
    {
      id: 'resourceAs', step: '4', label: 'Resource AS', sublabel: 'Local policy + token',
      x: 702, y: 112, w: 190, h: 104, color: '#0f766e',
      plain: 'The target system keeps control. Its authorization server decides whether to issue a scoped token.',
      technical: 'It validates the ID-JAG, resolves the user, applies local policy, and issues its own short-lived access token.',
    },
  ];

  if (fgaEnabled) {
    common.push({
      id: 'fga', step: '5', label: 'FGA', sublabel: 'Advanced context',
      x: 934, y: 112, w: 144, h: 104, color: '#7c3aed',
      plain: 'For inventory writes, the demo also checks role, quantity, and vacation status.',
      technical: 'The live FGA decision returns execute, request approval, or block. OAuth scopes remain the first boundary.',
    });
  }

  common.push({
    id: 'api', step: fgaEnabled ? '6' : '5', label: 'Inventory API', sublabel: 'Protected action',
    x: fgaEnabled ? 1116 : 1048, y: 112, w: 164, h: 104, color: '#16a34a',
    plain: 'Inventory is reached only after the required identity and access checks succeed.',
    technical: 'The API validates the final access token and enforces the requested read or write scope.',
  });

  return common;
}

function edgeData(fgaEnabled: boolean, agentActive: boolean): ArchitectureEdge[] {
  const edges: ArchitectureEdge[] = [
    { from: 'user', to: 'agent', label: 'asks' },
    { from: 'agent', to: 'idjag', label: agentActive ? 'agent + user' : 'exchange stopped', blocked: !agentActive },
    { from: 'idjag', to: 'resourceAs', label: 'ID-JAG', dimmed: !agentActive },
  ];

  if (fgaEnabled) {
    edges.push(
      { from: 'resourceAs', to: 'fga', label: 'scoped token', dimmed: !agentActive },
      { from: 'fga', to: 'api', label: 'decision', dimmed: !agentActive }
    );
  } else {
    edges.push({ from: 'resourceAs', to: 'api', label: 'scoped token', dimmed: !agentActive });
  }

  return edges;
}

interface D3ArchitectureDiagramProps {
  title?: string;
}

export default function D3ArchitectureDiagram({ title = 'The governed access chain' }: D3ArchitectureDiagramProps) {
  const { isEnabled: fgaEnabled, setIsEnabled: setFgaEnabled } = useFGASimulation();
  const [agentActive, setAgentActive] = useState(true);
  const [selectedId, setSelectedId] = useState<NodeId>('agent');

  const nodes = useMemo(() => nodeData(fgaEnabled), [fgaEnabled]);
  const edges = useMemo(() => edgeData(fgaEnabled, agentActive), [fgaEnabled, agentActive]);
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const selectedNode = nodeById.get(selectedId) ?? nodes[1];

  const isNodeDimmed = (id: NodeId) => !agentActive && ['idjag', 'resourceAs', 'fga', 'api'].includes(id);
  const outcomeLabel = agentActive ? (fgaEnabled ? 'FGA decision' : 'Scoped decision') : 'Stopped before exchange';

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
        <div className="border-b border-slate-200 px-5 py-5 dark:border-slate-800 sm:px-7">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">Architecture diagram</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950 dark:text-white">{title}</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
                The person and agent stay distinct from sign-in to business action. Select a node to go deeper.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setFgaEnabled(!fgaEnabled)}
                aria-pressed={fgaEnabled}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  fgaEnabled
                    ? 'border-violet-300 bg-violet-50 text-violet-800 dark:border-violet-700 dark:bg-violet-950/50 dark:text-violet-200'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-violet-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
                }`}
              >
                <Sparkles className="h-4 w-4" />
                FGA layer {fgaEnabled ? 'on' : 'off'}
              </button>
              <button
                type="button"
                onClick={() => setAgentActive(!agentActive)}
                aria-pressed={!agentActive}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  agentActive
                    ? 'border-red-200 bg-white text-red-700 hover:bg-red-50 dark:border-red-900 dark:bg-slate-900 dark:text-red-300 dark:hover:bg-red-950/40'
                    : 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200'
                }`}
              >
                <Power className="h-4 w-4" />
                {agentActive ? 'Simulate deactivation' : 'Reactivate simulation'}
              </button>
            </div>
          </div>

          <div className={`mt-5 flex items-start gap-3 rounded-xl border px-4 py-3 ${
            agentActive
              ? 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-900 dark:bg-emerald-950/30'
              : 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/40'
          }`}>
            {agentActive
              ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
              : <ShieldX className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />}
            <div>
              <p className={`text-sm font-bold ${agentActive ? 'text-emerald-900 dark:text-emerald-100' : 'text-red-900 dark:text-red-100'}`}>
                {agentActive ? 'Agent identity active: new delegated exchanges may continue.' : 'Agent identity deactivated: Okta rejects new delegated exchanges.'}
              </p>
              <p className="mt-0.5 text-xs leading-5 text-slate-600 dark:text-slate-300">
                {agentActive
                  ? 'Okta can still apply user, client, resource, and scope policy on every exchange.'
                  : 'No new ID-JAG means no new resource token. Previously issued short-lived tokens expire according to policy.'}
                {' '}This control is a visual simulation only; it does not change the live Okta tenant.
              </p>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto bg-slate-50/70 p-2 dark:bg-slate-900/40 sm:p-4">
          <p className="px-2 pb-2 text-[11px] font-semibold text-slate-500 dark:text-slate-400 sm:hidden">Swipe to follow the delegated access chain →</p>
          <svg
            viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
            className="block min-w-[940px] w-full"
            role="img"
            aria-label="Architecture diagram showing a signed-in employee, ProGear AI Agent Workload Principal, Okta ID-JAG, Resource Authorization Server, optional FGA context, and Inventory API"
          >
            <defs>
              <marker id="architecture-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
              </marker>
              <marker id="architecture-arrow-blocked" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#dc2626" />
              </marker>
              <filter id="architecture-shadow" x="-20%" y="-20%" width="140%" height="150%">
                <feDropShadow dx="0" dy="5" stdDeviation="7" floodColor="#0f172a" floodOpacity="0.12" />
              </filter>
            </defs>

            <text x={24} y={38} className="fill-slate-500 text-[11px] font-bold uppercase tracking-widest dark:fill-slate-400">Delegated access path</text>
            <g transform="translate(1028,18)">
              <rect width={228} height={34} rx={17} fill={agentActive ? '#ecfdf5' : '#fef2f2'} stroke={agentActive ? '#86efac' : '#fca5a5'} />
              <circle cx={18} cy={17} r={5} fill={agentActive ? '#16a34a' : '#dc2626'} />
              <text x={32} y={21} fill={agentActive ? '#166534' : '#991b1b'} className="text-[11px] font-bold">
                {agentActive ? 'New token exchange available' : 'New token exchange stopped'}
              </text>
            </g>

            {edges.map((edge) => {
              const from = nodeById.get(edge.from)!;
              const to = nodeById.get(edge.to)!;
              const midX = (from.x + from.w + to.x) / 2;
              const labelWidth = Math.max(58, edge.label.length * 6 + 16);
              const labelY = 72;
              const color = edge.blocked ? '#dc2626' : '#64748b';
              return (
                <g key={`${edge.from}-${edge.to}`} opacity={edge.dimmed ? 0.24 : 1}>
                  <path
                    d={connectorPath(from, to)}
                    fill="none"
                    stroke={color}
                    strokeWidth={edge.blocked ? 3 : 2.2}
                    strokeDasharray={edge.blocked ? '8 6' : undefined}
                    markerEnd={edge.blocked ? 'url(#architecture-arrow-blocked)' : 'url(#architecture-arrow)'}
                  />
                  <rect x={midX - labelWidth / 2} y={labelY} width={labelWidth} height={22} rx={11} className="fill-white stroke-slate-200 dark:fill-slate-950 dark:stroke-slate-700" />
                  <text x={midX} y={labelY + 15} textAnchor="middle" fill={color} className="text-[10px] font-semibold">{edge.label}</text>
                  {edge.blocked && (
                    <g transform={`translate(${midX - 11},184)`}>
                      <circle cx={11} cy={11} r={11} fill="#dc2626" />
                      <line x1={5} y1={11} x2={17} y2={11} stroke="white" strokeWidth={2.5} strokeLinecap="round" />
                    </g>
                  )}
                </g>
              );
            })}

            {nodes.map((node) => {
              const selected = selectedNode.id === node.id;
              const dimmed = isNodeDimmed(node.id);
              return (
                <g
                  key={node.id}
                  onClick={() => setSelectedId(node.id)}
                  className="cursor-pointer outline-none"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') setSelectedId(node.id);
                  }}
                  aria-label={`${node.label}: ${node.sublabel}`}
                  opacity={dimmed ? 0.3 : 1}
                  filter={selected ? 'url(#architecture-shadow)' : undefined}
                >
                  <rect
                    x={node.x}
                    y={node.y}
                    width={node.w}
                    height={node.h}
                    rx={16}
                    className="fill-white dark:fill-slate-950"
                    stroke={selected ? node.color : '#cbd5e1'}
                    strokeWidth={selected ? 3 : 1.5}
                  />
                  <rect x={node.x} y={node.y} width={7} height={node.h} rx={3.5} fill={node.color} />
                  <circle cx={node.x + 25} cy={node.y + 24} r={12} fill={node.color} />
                  <text x={node.x + 25} y={node.y + 28} textAnchor="middle" fill="white" className="text-[10px] font-bold">{node.step}</text>
                  <text x={node.x + 18} y={node.y + 61} className="fill-slate-950 text-[13px] font-bold dark:fill-white">{node.label}</text>
                  <text x={node.x + 18} y={node.y + 81} className="fill-slate-500 text-[10px] dark:fill-slate-400">{node.sublabel}</text>
                  {node.id === 'agent' && (
                    <g transform={`translate(${node.x + 18},${node.y + 96})`}>
                      <rect width={agentActive ? 70 : 92} height={22} rx={11} fill={agentActive ? '#dcfce7' : '#fee2e2'} />
                      <circle cx={12} cy={11} r={4} fill={agentActive ? '#16a34a' : '#dc2626'} />
                      <text x={22} y={15} fill={agentActive ? '#166534' : '#991b1b'} className="text-[9px] font-bold">
                        {agentActive ? 'ACTIVE' : 'DEACTIVATED'}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            <g transform="translate(24,278)">
              <rect width={1232} height={48} rx={14} className="fill-white stroke-slate-200 dark:fill-slate-950 dark:stroke-slate-700" />
              <text x={18} y={20} className="fill-slate-500 text-[9px] font-bold uppercase tracking-widest dark:fill-slate-400">Accountability trail</text>
              <text x={18} y={37} className="fill-slate-900 text-[11px] font-semibold dark:fill-white">Sarah Sales</text>
              <text x={123} y={37} className="fill-slate-400 text-[12px]">→</text>
              <text x={151} y={37} className="fill-slate-900 text-[11px] font-semibold dark:fill-white">ProGear Agent (wlp...)</text>
              <text x={310} y={37} className="fill-slate-400 text-[12px]">→</text>
              <text x={339} y={37} className="fill-slate-900 text-[11px] font-semibold dark:fill-white">Inventory</text>
              <text x={414} y={37} className="fill-slate-400 text-[12px]">→</text>
              <text x={443} y={37} className="fill-slate-900 text-[11px] font-semibold dark:fill-white">inventory:read</text>
              {fgaEnabled && (
                <>
                  <text x={557} y={37} className="fill-slate-400 text-[12px]">→</text>
                  <text x={585} y={37} className="fill-violet-700 text-[11px] font-semibold dark:fill-violet-300">role + quantity + vacation</text>
                </>
              )}
              <g transform={`translate(${fgaEnabled ? 980 : 840},9)`}>
                <rect width={agentActive ? 218 : 242} height={30} rx={15} fill={agentActive ? '#ecfdf5' : '#fef2f2'} />
                <circle cx={16} cy={15} r={5} fill={agentActive ? '#16a34a' : '#dc2626'} />
                <text x={29} y={19} fill={agentActive ? '#166534' : '#991b1b'} className="text-[10px] font-bold">Outcome: {outcomeLabel}</text>
              </g>
            </g>
          </svg>
        </div>

        <div className="grid gap-4 border-t border-slate-200 p-5 dark:border-slate-800 sm:grid-cols-[0.9fr,1.1fr] sm:p-7">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg text-white" style={{ backgroundColor: selectedNode.color }}>
                {selectedNode.id === 'agent' ? <Fingerprint className="h-4 w-4" /> : <Activity className="h-4 w-4" />}
              </span>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">Selected control point</p>
                <h3 className="font-bold text-slate-950 dark:text-white">{selectedNode.label}</h3>
              </div>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedNode.plain}</p>
          </div>
          <div className="rounded-xl bg-blue-50/70 p-4 dark:bg-blue-950/30">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-blue-700 dark:text-blue-300">
              <Braces className="h-4 w-4" /> Engineer view
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-800 dark:text-slate-200">{selectedNode.technical}</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          {
            icon: Fingerprint,
            title: 'The agent is an identity',
            body: 'Owners, credentials, lifecycle, and resource connections attach to one governed Workload Principal.',
          },
          {
            icon: ArrowRight,
            title: 'Delegation is not impersonation',
            body: 'The employee stays the subject while the agent client remains visible as the party acting on that person’s behalf.',
          },
          {
            icon: CircleStop,
            title: 'Revocation has a control point',
            body: 'Deactivate the agent identity to prevent new exchanges—without changing prompts, tools, or deployment code.',
          },
        ].map(({ icon: Icon, title: cardTitle, body }) => (
          <div key={cardTitle} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-950">
            <Icon className="h-5 w-5 text-orange-600 dark:text-orange-400" />
            <h3 className="mt-3 font-bold text-slate-950 dark:text-white">{cardTitle}</h3>
            <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{body}</p>
          </div>
        ))}
      </div>

      <SequenceDiagram agentActive={agentActive} fgaEnabled={fgaEnabled} />

      <details className="group rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-semibold text-slate-950 dark:text-white sm:px-7">
          <span className="flex items-center gap-2"><BookOpen className="h-5 w-5 text-blue-600 dark:text-blue-400" /> Standards and implementation notes for AI engineers</span>
          <span className="text-sm text-slate-400 transition group-open:rotate-90">›</span>
        </summary>
        <div className="grid gap-5 border-t border-slate-200 px-5 py-5 text-sm leading-6 text-slate-700 dark:border-slate-800 dark:text-slate-200 sm:grid-cols-2 sm:px-7">
          <div>
            <h3 className="font-bold text-slate-950 dark:text-white">Identity continuity</h3>
            <p className="mt-1">The ID-JAG identifies the end user, the authenticated client that will act for that user, and the target Resource Authorization Server. The target still owns subject resolution and authorization policy.</p>
          </div>
          <div>
            <h3 className="font-bold text-slate-950 dark:text-white">Operational boundary</h3>
            <p className="mt-1">Agent deactivation blocks new exchanges. Keep resource access tokens short-lived and enforce their signature, issuer, audience, expiry, and scopes at every API.</p>
          </div>
          <div className="sm:col-span-2 flex flex-wrap gap-3">
            <a className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:underline dark:text-blue-300" href="https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant" target="_blank" rel="noreferrer">IETF ID-JAG draft <ArrowRight className="h-3.5 w-3.5" /></a>
            <a className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:underline dark:text-blue-300" href="https://xaa.dev/" target="_blank" rel="noreferrer">Cross App Access <ArrowRight className="h-3.5 w-3.5" /></a>
            <a className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:underline dark:text-blue-300" href="https://developer.okta.com/docs/api/secures-ai/ai-agents" target="_blank" rel="noreferrer">Okta AI Agents API <ArrowRight className="h-3.5 w-3.5" /></a>
          </div>
        </div>
      </details>
    </div>
  );
}
