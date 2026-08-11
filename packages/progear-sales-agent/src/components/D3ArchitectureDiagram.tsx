'use client';

import { useMemo, useState } from 'react';
import { curveBumpX, line } from 'd3-shape';
import { Power, Sparkles } from 'lucide-react';
import { useFGASimulation } from '@/hooks/useFGASimulation';
import SequenceDiagram from './SequenceDiagram';

type NodeId =
  | 'kill'
  | 'user'
  | 'agent'
  | 'okta'
  | 'resourceAs'
  | 'fga'
  | 'audit'
  | 'inventory'
  | 'customer'
  | 'pricing'
  | 'sales';

interface GraphNode {
  id: NodeId;
  label: string;
  sublabel: string;
  detail: string;
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  compact?: boolean;
  resource?: boolean;
}

interface GraphEdge {
  id: string;
  from: NodeId;
  to: NodeId;
  path: string;
  label?: string;
  labelX?: number;
  labelY?: number;
  blocked?: boolean;
  downstream?: boolean;
}

const VIEW_W = 1200;
const VIEW_H = 515;

const COLORS = {
  user: '#8b5cf6',
  agent: '#f97316',
  okta: '#3b82f6',
  authz: '#0f766e',
  fga: '#7c3aed',
  resource: '#4d9f45',
  audit: '#64748b',
  danger: '#dc2626',
} as const;

function curve(points: Array<[number, number]>): string {
  return line<[number, number]>().curve(curveBumpX)(points) ?? '';
}

function graphNodes(fgaEnabled: boolean): GraphNode[] {
  const nodes: GraphNode[] = [
    {
      id: 'kill', label: 'Kill switch', sublabel: 'Deactivate identity',
      detail: 'Deactivation stops new agent authentication and ID-JAG exchanges.',
      x: 225, y: 30, w: 160, h: 48, color: COLORS.danger, compact: true,
    },
    {
      id: 'user', label: 'Employee', sublabel: 'Signed-in subject',
      detail: 'The employee remains the delegated request subject.',
      x: 25, y: 235, w: 150, h: 74, color: COLORS.user,
    },
    {
      id: 'agent', label: 'ProGear Agent', sublabel: 'Workload Principal',
      detail: 'First-class agent identity: wlp… + private_key_jwt.',
      x: 225, y: 220, w: 185, h: 104, color: COLORS.agent,
    },
    {
      id: 'okta', label: 'Okta', sublabel: 'Identity + ID-JAG',
      detail: 'Issues the delegated grant for user + agent client + target.',
      x: 490, y: 45, w: 180, h: 82, color: COLORS.okta,
    },
    {
      id: 'resourceAs', label: 'Resource AS', sublabel: 'Policy + scoped token',
      detail: 'Validates ID-JAG, applies local policy, and issues a resource token.',
      x: 490, y: 225, w: 180, h: 94, color: COLORS.authz,
    },
    {
      id: 'audit', label: 'Audit trail', sublabel: 'Exchange + decision',
      detail: 'Correlates user, agent, resource, scope, and outcome.',
      x: 490, y: 410, w: 180, h: 64, color: COLORS.audit,
    },
    {
      id: 'inventory', label: 'Inventory', sublabel: 'read / write',
      detail: 'Inventory accepts only a valid token with the required scope.',
      x: 1000, y: 50, w: 175, h: 70, color: COLORS.resource, resource: true,
    },
    {
      id: 'customer', label: 'Customer', sublabel: 'read',
      detail: 'Customer data has its own resource boundary and scope.',
      x: 1000, y: 155, w: 175, h: 70, color: COLORS.resource, resource: true,
    },
    {
      id: 'pricing', label: 'Pricing', sublabel: 'read / margin / discount',
      detail: 'Pricing has its own scopes and resource policy.',
      x: 1000, y: 260, w: 175, h: 70, color: COLORS.resource, resource: true,
    },
    {
      id: 'sales', label: 'Sales', sublabel: 'read / quote / order',
      detail: 'Sales has its own scopes and resource policy.',
      x: 1000, y: 365, w: 175, h: 70, color: COLORS.resource, resource: true,
    },
  ];

  if (fgaEnabled) {
    nodes.push({
      id: 'fga', label: 'FGA', sublabel: 'role + quantity',
      detail: 'Inventory decision: execute, OIG approval, or block.',
      x: 755, y: 40, w: 190, h: 90, color: COLORS.fga,
    });
  }

  return nodes;
}

function graphEdges(fgaEnabled: boolean, agentActive: boolean): GraphEdge[] {
  const edges: GraphEdge[] = [
    {
      id: 'kill-agent', from: 'kill', to: 'agent',
      path: 'M305 78 L305 220',
      blocked: !agentActive,
    },
    {
      id: 'user-agent', from: 'user', to: 'agent',
      path: curve([[175, 272], [225, 272]]),
      label: 'request', labelX: 200, labelY: 252,
    },
    {
      id: 'agent-okta', from: 'agent', to: 'okta',
      path: 'M318 220 C318 158 402 86 490 86',
      label: agentActive ? 'authenticate' : 'exchange stopped', labelX: 410, labelY: 148,
      blocked: !agentActive,
    },
    {
      id: 'okta-resource', from: 'okta', to: 'resourceAs',
      path: 'M580 127 L580 225',
      label: 'ID-JAG', labelX: 620, labelY: 181,
      downstream: true,
    },
    {
      id: 'resource-audit', from: 'resourceAs', to: 'audit',
      path: 'M580 319 L580 410',
      label: 'log', labelX: 610, labelY: 369,
      downstream: true,
    },
  ];

  const resourceStartX = 670;
  if (fgaEnabled) {
    edges.push(
      {
        id: 'resource-fga', from: 'resourceAs', to: 'fga',
        path: curve([[resourceStartX, 246], [755, 85]]),
        label: 'inventory token', labelX: 720, labelY: 150,
        downstream: true,
      },
      {
        id: 'fga-inventory', from: 'fga', to: 'inventory',
        path: curve([[945, 85], [1000, 85]]),
        label: 'decision', labelX: 972, labelY: 65,
        downstream: true,
      }
    );
  } else {
    edges.push({
      id: 'resource-inventory', from: 'resourceAs', to: 'inventory',
      path: curve([[resourceStartX, 244], [1000, 85]]),
      downstream: true,
    });
  }

  edges.push(
    { id: 'resource-customer', from: 'resourceAs', to: 'customer', path: curve([[resourceStartX, 265], [1000, 190]]), downstream: true },
    { id: 'resource-pricing', from: 'resourceAs', to: 'pricing', path: curve([[resourceStartX, 283], [1000, 295]]), downstream: true },
    { id: 'resource-sales', from: 'resourceAs', to: 'sales', path: curve([[resourceStartX, 302], [1000, 400]]), downstream: true }
  );

  return edges;
}

interface D3ArchitectureDiagramProps {
  title?: string;
}

export default function D3ArchitectureDiagram({ title = 'System architecture' }: D3ArchitectureDiagramProps) {
  const { isEnabled: fgaEnabled, setIsEnabled: setFgaEnabled } = useFGASimulation();
  const [agentActive, setAgentActive] = useState(true);
  const [selectedId, setSelectedId] = useState<NodeId>('agent');
  const [hoveredId, setHoveredId] = useState<NodeId | null>(null);

  const nodes = useMemo(() => graphNodes(fgaEnabled), [fgaEnabled]);
  const edges = useMemo(() => graphEdges(fgaEnabled, agentActive), [fgaEnabled, agentActive]);
  const selectedNode = nodes.find((node) => node.id === selectedId) ?? nodes[2];
  const activeId = hoveredId ?? selectedId;

  const isDownstream = (id: NodeId) => ['okta', 'resourceAs', 'fga', 'audit', 'inventory', 'customer', 'pricing', 'sales'].includes(id);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-[#0b0f1a]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800 sm:px-6">
          <div>
            <h2 className="font-bold text-slate-950 dark:text-white">{title}</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Hover to trace · click a node for detail</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setFgaEnabled(!fgaEnabled)}
              aria-pressed={fgaEnabled}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                fgaEnabled
                  ? 'border-violet-400 bg-violet-50 text-violet-800 dark:bg-violet-950/60 dark:text-violet-200'
                  : 'border-slate-300 text-slate-700 hover:border-violet-400 dark:border-slate-700 dark:text-slate-200'
              }`}
            >
              <Sparkles className="h-4 w-4" /> FGA {fgaEnabled ? 'on' : 'off'}
            </button>
            <button
              type="button"
              onClick={() => setAgentActive(!agentActive)}
              aria-pressed={!agentActive}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                agentActive
                  ? 'border-red-300 text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/30'
                  : 'border-emerald-400 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200'
              }`}
            >
              <Power className="h-4 w-4" /> {agentActive ? 'Test kill switch' : 'Reactivate'}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto bg-slate-50/70 dark:bg-[#0d111c]">
          <p className="px-5 pt-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400 sm:hidden">Swipe to follow the architecture →</p>
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="block min-w-[900px] w-full"
            role="img"
            aria-label="ProGear architecture showing the user, governed AI agent, Okta ID-JAG exchange, Resource Authorization Server, optional FGA decision, audit trail, and business resources"
          >
            <defs>
              <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0 0 L10 5 L0 10 Z" fill="#94a3b8" />
              </marker>
              <marker id="arch-arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0 0 L10 5 L0 10 Z" fill="#f97316" />
              </marker>
              <marker id="arch-arrow-blocked" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0 0 L10 5 L0 10 Z" fill="#dc2626" />
              </marker>
              <filter id="arch-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#f97316" floodOpacity="0.35" />
              </filter>
            </defs>

            <text x={25} y={28} className="fill-slate-500 text-[10px] font-bold uppercase tracking-[0.16em] dark:fill-slate-400">Identity and access control plane</text>
            <text x={1000} y={28} className="fill-slate-500 text-[10px] font-bold uppercase tracking-[0.16em] dark:fill-slate-400">Business resources</text>

            {edges.map((edge) => {
              const connected = edge.id !== 'kill-agent' && (activeId === edge.from || activeId === edge.to);
              const inactive = !agentActive && edge.downstream;
              const blocked = Boolean(edge.blocked);
              return (
                <g key={edge.id} opacity={inactive ? 0.32 : 1}>
                  <path
                    d={edge.path}
                    fill="none"
                    className={blocked ? 'stroke-red-600' : connected ? 'stroke-orange-500' : 'stroke-slate-500 dark:stroke-slate-300'}
                    strokeWidth={blocked || connected ? 4 : 3}
                    strokeDasharray={blocked ? '8 6' : undefined}
                    strokeLinecap="round"
                    markerEnd={blocked ? 'url(#arch-arrow-blocked)' : connected ? 'url(#arch-arrow-active)' : 'url(#arch-arrow)'}
                  />
                  {edge.label && edge.labelX !== undefined && edge.labelY !== undefined ? (
                    <g>
                      <rect
                        x={edge.labelX - Math.max(28, edge.label.length * 3.2)}
                        y={edge.labelY - 12}
                        width={Math.max(56, edge.label.length * 6.4)}
                        height={22}
                        rx={11}
                        className="fill-white stroke-slate-200 dark:fill-[#0d111c] dark:stroke-slate-700"
                      />
                      <text
                        x={edge.labelX}
                        y={edge.labelY + 3}
                        textAnchor="middle"
                        className={blocked ? 'fill-red-600 text-[10px] font-bold' : connected ? 'fill-orange-600 text-[10px] font-bold dark:fill-orange-400' : 'fill-slate-600 text-[10px] font-semibold dark:fill-slate-200'}
                      >
                        {edge.label}
                      </text>
                    </g>
                  ) : null}
                </g>
              );
            })}

            {nodes.map((node) => {
              const active = activeId === node.id;
              const inactive = !agentActive && isDownstream(node.id);
              const statusLabel = node.id === 'agent' ? (agentActive ? 'ACTIVE' : 'DEACTIVATED') : null;
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x},${node.y})`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${node.label}: ${node.sublabel}`}
                  className="cursor-pointer outline-none"
                  opacity={inactive ? 0.42 : activeId && !active ? 0.82 : 1}
                  filter={active ? 'url(#arch-glow)' : undefined}
                  onMouseEnter={() => setHoveredId(node.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => setSelectedId(node.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') setSelectedId(node.id);
                  }}
                >
                  <rect
                    width={node.w}
                    height={node.h}
                    rx={node.compact ? 20 : 13}
                    className="fill-white dark:fill-[#111827]"
                    stroke={active ? node.color : '#64748b'}
                    strokeWidth={active ? 3 : 1.7}
                  />
                  <rect x={0} y={0} width={6} height={node.h} rx={3} fill={node.color} />
                  <circle cx={node.compact ? 19 : 22} cy={node.compact ? 24 : 25} r={5} fill={node.color} />
                  <text x={node.compact ? 32 : 38} y={node.compact ? 28 : 29} className="fill-slate-950 text-[12px] font-bold dark:fill-white">{node.label}</text>
                  <text x={node.compact ? 32 : 18} y={node.compact ? 43 : 50} className="fill-slate-500 text-[9px] dark:fill-slate-400">{node.sublabel}</text>
                  {node.id === 'agent' ? (
                    <g transform="translate(18,67)">
                      <rect width={agentActive ? 69 : 98} height={22} rx={11} fill={agentActive ? '#dcfce7' : '#fee2e2'} />
                      <circle cx={12} cy={11} r={4} fill={agentActive ? '#16a34a' : '#dc2626'} />
                      <text x={22} y={15} fill={agentActive ? '#166534' : '#991b1b'} className="text-[9px] font-bold">{statusLabel}</text>
                    </g>
                  ) : null}
                  {node.id === 'fga' ? (
                    <g transform="translate(18,61)">
                      <text className="fill-violet-700 text-[9px] font-bold dark:fill-violet-300">ALLOW · OIG · BLOCK</text>
                    </g>
                  ) : null}
                </g>
              );
            })}

            {!agentActive ? (
              <g transform="translate(432,191)">
                <circle cx={0} cy={0} r={13} fill="#dc2626" />
                <line x1={-6} y1={0} x2={6} y2={0} stroke="white" strokeWidth={3} strokeLinecap="round" />
              </g>
            ) : null}
          </svg>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-200 px-5 py-3 text-sm dark:border-slate-800 sm:px-6">
          <span className="font-bold text-slate-950 dark:text-white">{selectedNode.label}</span>
          <span className="hidden text-slate-300 dark:text-slate-700 sm:inline">|</span>
          <span className="text-slate-600 dark:text-slate-300">{selectedNode.detail}</span>
        </div>
      </section>

      <SequenceDiagram agentActive={agentActive} fgaEnabled={fgaEnabled} />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-1 text-xs text-slate-500 dark:text-slate-400">
        <span className="font-semibold text-slate-700 dark:text-slate-300">References</span>
        <a className="hover:text-blue-600 hover:underline dark:hover:text-blue-300" href="https://developer.okta.com/docs/api/secures-ai/ai-agents" target="_blank" rel="noreferrer">Workload Principal</a>
        <a className="hover:text-blue-600 hover:underline dark:hover:text-blue-300" href="https://datatracker.ietf.org/doc/html/draft-ietf-oauth-identity-assertion-authz-grant" target="_blank" rel="noreferrer">ID-JAG</a>
        <a className="hover:text-blue-600 hover:underline dark:hover:text-blue-300" href="https://xaa.dev/" target="_blank" rel="noreferrer">Cross App Access</a>
      </div>
    </div>
  );
}
