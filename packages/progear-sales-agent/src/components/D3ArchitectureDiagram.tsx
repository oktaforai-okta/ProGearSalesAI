'use client';

/**
 * D3ArchitectureDiagram — the customer-facing "how it works" experience.
 *
 * Two modes with two different jobs, deliberately using two different
 * visual paradigms:
 * - Overview: "what are the pieces and how do they relate" — a resting
 *   hub-and-spoke relationship graph, hover-to-trace, click-for-detail.
 *   A graph is the right tool for a static relationship question.
 * - Watch a request: "what happens, in what order" — delegated entirely to
 *   <SequenceDiagram>, a UML-style lane diagram. An earlier version tried to
 *   answer this temporal question by animating a dot along this same graph;
 *   repeated feedback ("lines crossing", "can't connect the dots") confirmed
 *   that doesn't work, because a hub-and-spoke graph has no stable "forward"
 *   direction for a dot to follow. Sequence is a different question with a
 *   different right tool, so it gets a different component.
 *
 * Pattern: HYBRID (verified against this app's real strict-mode tsconfig).
 * React owns all state, the SVG element, and every node/label as JSX so
 * click/hover stay native-React and drive the side panel + highlight state.
 * D3 owns only the interior of one <g ref> — the edge paths — via a keyed
 * data-join in useEffect, plus imperative attr mutation for hover-highlight.
 * D3 never touches the DOM during SSR; everything DOM-facing lives in
 * effects that run client-side post-mount.
 *
 * Layout is FIXED (authored x/y), not d3-force — a small, known graph reads
 * as a stable story every load.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { select, type Selection } from 'd3-selection';
import { line, curveBumpX } from 'd3-shape';
import SequenceDiagram from './SequenceDiagram';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Mode = 'overview' | 'flow';

interface NodeDetail {
  body: string;
  subpoints?: string[];
  callouts?: string[];
  architect?: string;
  // A decoded (illustrative, not real) token payload shown to architects
  // so they can see the actual claim shape instead of just prose about
  // it. Values are made up for illustration -- never a real token.
  tokenExample?: { label: string; json: string };
}

interface DiagramNode {
  id: string;
  label: string;
  sublabel: string;
  x: number;
  y: number;
  w: number;
  h: number;
  accent: string;
  hero?: boolean;
  dim?: boolean;
  chip?: boolean;
  order?: number;
  description: string;
  detail: NodeDetail;
}

interface PhysicalEdge {
  id: string;
  source: string;
  target: string;
}

// ---------------------------------------------------------------------------
// Brand palette — mirrors tailwind.config.js so SVG fills match the app.
// Color = meaning: blue = Okta/identity, orange = access/action, purple =
// human/governance, green = business data (reached only after checks pass).
// ---------------------------------------------------------------------------

const C = {
  oktaBlue: '#007dc1',
  accent: '#ff6b35',
  purple: '#8b5cf6',
  green: '#22c55e',
  deny: '#ef4444',
  slate: '#334155',
  edge: '#475569',
  edgeActive: '#ff6b35',
  nodeFill: '#16213e',
  text: '#e2e8f0',
  textDim: '#94a3b8',
} as const;

const VIEW_W = 1040;
const VIEW_H = 620;

// ---------------------------------------------------------------------------
// Data model — 8 nodes across 3 tiers (actor / trust / resource), 7 edges.
// Content verified against the app's actual code (backend/auth/agent_config.py,
// fga_client.py, services/factory.py::APPROVAL_QUANTITY_THRESHOLD=500), not
// assumed — see SequenceDiagram.tsx for the note chips carrying the exact
// scope strings and the confirmed 500-unit approval threshold.
// ---------------------------------------------------------------------------

const NODES: DiagramNode[] = [
  {
    id: 'you',
    label: 'User',
    sublabel: 'Signed-in person',
    x: 76, y: 320, w: 150, h: 70,
    accent: C.purple,
    order: 1,
    description: 'The signed-in person asking a question in plain English.',
    detail: {
      body: "The signed-in person asking a question. Okta verifies who you are — the AI acts on your behalf, within your limits, never on its own.",
      callouts: ['Verified by Okta login', 'Role determines what you can do'],
    },
  },
  {
    id: 'ai',
    label: 'AI Agent',
    sublabel: 'Understands + routes',
    x: 300, y: 320, w: 150, h: 70,
    accent: C.oktaBlue,
    order: 2,
    description: 'The chatbot that understands your request and figures out which systems it needs.',
    detail: {
      body: "Reads your question and routes it to the right systems. It never decides what you're allowed to see — that's Okta's job, not the AI's.",
      callouts: ['Has its own Okta identity (a Workload Principal)', 'No standing access of its own'],
      architect: 'Claude via the raw Anthropic SDK — wording and routing only, not the security boundary.',
      tokenExample: {
        label: 'Step 1: the ID-JAG assertion',
        json: `{
  "sub": "mike@example.com",
  "act": {
    "sub": "wlpuoor63yK6..."
  },
  "exp": 1751500060
}`,
      },
    },
  },
  {
    id: 'okta',
    label: 'Okta',
    sublabel: 'Identity + Access',
    x: 560, y: 120, w: 150, h: 70,
    accent: C.oktaBlue,
    hero: true,
    order: 3,
    description: 'Issues a short-lived, single-purpose pass every time the AI needs to touch a system.',
    detail: {
      body: "Before the AI touches any system, it asks Okta for permission. Okta checks who you are and whether your role allows this — then issues a short-lived, single-purpose pass, or refuses.",
      subpoints: [
        "Every system has its own separate pass. A pass for pricing can't open inventory.",
        'Passes expire in minutes, so a leaked one is near-worthless.',
        'The AI never holds a master key. It gets a fresh, narrow pass each time.',
      ],
      callouts: ['Passes are scoped per system + per action', "All-or-nothing: if a role can't do it, the whole request is refused"],
      architect: 'Two-step ID-JAG exchange. 4 separate Custom Authorization Servers (one per domain) — no down-scoping.',
      tokenExample: {
        label: 'Step 2: the scoped access token',
        json: `{
  "aud": "progear-inventory",
  "sub": "mike@example.com",
  "scp": [
    "inventory:write"
  ],
  "Manager": true,
  "Vacation": false,
  "Clearance": 5,
  "exp": 1751500300
}`,
      },
    },
  },
  {
    id: 'fga',
    label: 'Access Rules',
    sublabel: 'Relationship + context check',
    x: 610, y: 300, w: 150, h: 70,
    accent: C.accent,
    hero: true,
    order: 4,
    description: 'A live check of your relationships and current context, like whether you manage this warehouse or are on vacation.',
    detail: {
      body: "A live check beyond your role: do you manage this warehouse? Is your clearance high enough? Are you on vacation? Any mismatch blocks access instantly.",
      subpoints: [
        'Relationship: are you the manager or an approved viewer of this specific warehouse?',
        'Clearance: higher clearance automatically includes everything below it.',
        "Context: a live flag (for example 'on vacation') can block access this second, with no code change.",
      ],
      callouts: ['Blocks instantly on context change', 'No redeploy needed to revoke'],
      architect: "Auth0 FGA (Zanzibar-style relationship graph). Vacation is a contextual tuple, not stored — takes effect next check.",
    },
  },
  {
    id: 'approval',
    label: 'Approval Gate',
    sublabel: 'Human Approval Only',
    x: 600, y: 505, w: 150, h: 70,
    accent: C.purple,
    order: 5,
    description: 'High-impact actions (like a large inventory change) pause here for a human to approve.',
    detail: {
      body: "High-impact writes pause for a real person to approve or deny. The AI can't push them through on its own.",
      subpoints: [
        'Triggered by impact (a write of 500 units or more), not by every action.',
        'A named human approves or denies. Fully audited.',
        'Nothing happens to the business system until sign-off lands.',
      ],
      callouts: ['Human-in-the-loop', 'Auto-resumes once approved'],
      architect: 'A real Okta Identity Governance (OIG) Access Request, created once a write crosses the 500-unit threshold.',
    },
  },
  {
    id: 'inventory',
    label: 'Inventory',
    sublabel: 'read / write / alerts',
    x: 945, y: 160, w: 150, h: 70,
    accent: C.green,
    description: 'Stock levels and adjustments.',
    detail: {
      body: 'Stock levels and adjustments. Reading is broadly allowed; large writes need approval and a manager relationship.',
    },
  },
  {
    id: 'customer',
    label: 'Customer',
    sublabel: 'read',
    x: 945, y: 280, w: 150, h: 70,
    accent: C.green,
    description: 'Customer accounts and history.',
    detail: {
      body: 'Customer accounts and history.',
    },
  },
  {
    id: 'pricing',
    label: 'Pricing',
    sublabel: 'read',
    x: 945, y: 400, w: 150, h: 70,
    accent: C.green,
    description: 'Product and deal pricing.',
    detail: {
      body: 'Product and deal pricing.',
    },
  },
  {
    id: 'sales',
    label: 'Sales',
    sublabel: 'read',
    x: 945, y: 520, w: 150, h: 70,
    accent: C.green,
    description: 'Orders, quotes, and pipeline.',
    detail: {
      body: 'Orders, quotes, and pipeline.',
    },
  },
  {
    id: 'audit',
    label: 'Audit Trail',
    sublabel: 'Every decision logged',
    x: 762, y: 120, w: 150, h: 70,
    accent: C.slate,
    dim: true,
    order: 6,
    description: 'A permanent, searchable record of every pass issued and every allow/deny decision.',
    detail: {
      body: "Every access decision — granted or denied — is logged instantly. Answers 'who did what, when, why' without trusting the AI to self-report.",
      callouts: ['Queryable', 'Covers grants AND denials'],
      architect: "Okta's System Log — a queryable, tamper-evident stream separate from this app's own logging.",
    },
  },
  {
    id: 'killswitch',
    label: 'Kill Switch',
    sublabel: 'Revoke in one click',
    x: 120, y: 70, w: 108, h: 34,
    accent: C.deny,
    dim: true,
    chip: true,
    description: "Turn off the AI's access instantly by deactivating its identity or flipping a context flag.",
    detail: {
      body: "One step cuts the AI's access: deactivate its identity, or flip a context flag. Takes effect almost immediately — no redeploy.",
      callouts: ['Deactivate identity — OR — flip a context flag'],
    },
  },
];

// The four business-domain boxes are siblings reached by one shared "bus"
// out of the AI hub, not a sequential chain -- this list is the single
// source of truth for that grouping so edge/highlight logic below never
// has to hardcode all four ids separately.
const BUSINESS_NODE_IDS = ['inventory', 'customer', 'pricing', 'sales'];
const BUSINESS_EDGE_IDS = BUSINESS_NODE_IDS.map((id) => `ai_${id}`);

const EDGES: PhysicalEdge[] = [
  { id: 'you_ai', source: 'you', target: 'ai' },
  { id: 'ai_okta', source: 'ai', target: 'okta' },
  { id: 'ai_fga', source: 'ai', target: 'fga' },
  { id: 'ai_approval', source: 'ai', target: 'approval' },
  { id: 'ai_inventory', source: 'ai', target: 'inventory' },
  { id: 'ai_customer', source: 'ai', target: 'customer' },
  { id: 'ai_pricing', source: 'ai', target: 'pricing' },
  { id: 'ai_sales', source: 'ai', target: 'sales' },
  { id: 'okta_audit', source: 'okta', target: 'audit' },
  { id: 'fga_audit', source: 'fga', target: 'audit' },
];

// ---------------------------------------------------------------------------
// Pure geometry helpers (no DOM; safe to call anywhere)
// ---------------------------------------------------------------------------

function findNode(list: DiagramNode[], id: string): DiagramNode {
  const n = list.find((n) => n.id === id);
  if (!n) throw new Error(`Unknown node id: ${id}`);
  return n;
}

const linkPath = line<[number, number]>()
  .x((d) => d[0])
  .y((d) => d[1])
  .curve(curveBumpX);

// Every business-domain edge shares the same first two waypoints, so they
// draw on top of each other from the AI hub through the open lane between
// the FGA box (bottom y=335) and the Approval Gate (top y=473) — around
// y=400 — reading as one trunk that only splits into four once it's clear
// of the trust tier. From the branch point (870,400) each edge takes its
// own short final hop up/down to its box, so none crosses the AI's other
// spokes nor the okta_audit / fga_audit edges.
const EDGE_WAYPOINTS: Record<string, Array<[number, number]>> = {
  ai_inventory: [[470, 400], [870, 400], [870, 160]],
  ai_customer: [[470, 400], [870, 400], [870, 280]],
  ai_pricing: [[470, 400], [870, 400]],
  ai_sales: [[470, 400], [870, 400], [870, 520]],
};

function edgePoints(edge: PhysicalEdge, nodes: DiagramNode[]): Array<[number, number]> {
  const s = findNode(nodes, edge.source);
  const t = findNode(nodes, edge.target);
  const mids = EDGE_WAYPOINTS[edge.id] ?? [];
  return [[s.x, s.y], ...mids, [t.x, t.y]];
}

function edgeD(edge: PhysicalEdge, nodes: DiagramNode[]): string {
  return linkPath(edgePoints(edge, nodes))!;
}

function pointAlongEdge(edge: PhysicalEdge, nodes: DiagramNode[], u: number): [number, number] {
  const pts = edgePoints(edge, nodes);
  const segLens: number[] = [];
  let total = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    segLens.push(d);
    total += d;
  }
  if (total === 0) return [pts[0][0], pts[0][1]];
  const target = Math.max(0, Math.min(1, u)) * total;
  let acc = 0;
  for (let i = 0; i < segLens.length; i++) {
    if (target <= acc + segLens[i] || i === segLens.length - 1) {
      const local = segLens[i] === 0 ? 0 : (target - acc) / segLens[i];
      return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * local, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * local];
    }
    acc += segLens[i];
  }
  return [pts[pts.length - 1][0], pts[pts.length - 1][1]];
}

const EDGE_LABELS: Record<string, string> = {
  you_ai: 'asks / answers',
  ai_okta: 'requests a pass ↔ issues one',
  ai_fga: 'checks context ↔ confirms',
  ai_approval: 'high-impact action',
  // Shown once, on the shared trunk -- applies to all four business edges,
  // so the other three intentionally have no entry here (see edge-label
  // render: a missing key just skips the label).
  ai_pricing: 'uses the pass ↔ returns data',
  okta_audit: 'logs the decision',
  fga_audit: 'logs the check',
};

// Each label is pushed off its edge midpoint along the edge's perpendicular
// normal by this many px, tuned so the two corridors fanning out of the AI
// node (ai_okta / ai_fga) sit on opposite sides and no anchor lands on a
// node. A semi-opaque pill is drawn behind each label so it stays legible.
const EDGE_LABEL_OFFSET: Record<string, number> = {
  ai_okta: -12,
  ai_fga: 16,
  ai_approval: 18,
  ai_pricing: -20,
  okta_audit: 50,
  fga_audit: -16,
};

const EDGE_LABEL_U: Record<string, number> = {};

interface DetachedLabel {
  x: number;
  y: number;
  anchorX: number;
  anchorY: number;
}

// Edges whose label can't sit on or near the line itself without being
// occluded by nearby node boxes (this file draws edge-label <g>s before
// node <g>s, so nodes paint on top) get lifted clear of the boxes
// entirely, with a short leader line + arrowhead pointing back down to
// the actual edge so it's still clear which edge the label belongs to.
const EDGE_LABEL_DETACHED: Record<string, DetachedLabel> = {
  you_ai: { x: 188, y: 260, anchorX: 188, anchorY: 320 },
};

function edgeLabelAnchor(edge: PhysicalEdge, nodes: DiagramNode[], offset: number, u = 0.5): [number, number] {
  const [px, py] = pointAlongEdge(edge, nodes, u);
  const [bx, by] = pointAlongEdge(edge, nodes, Math.max(0, u - 0.02));
  const [ax, ay] = pointAlongEdge(edge, nodes, Math.min(1, u + 0.02));
  const dx = ax - bx;
  const dy = ay - by;
  const len = Math.hypot(dx, dy) || 1;
  return [px + (-dy / len) * offset, py + (dx / len) * offset];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface D3ArchitectureDiagramProps {
  title?: string;
}

export default function D3ArchitectureDiagram({ title = 'Architecture' }: D3ArchitectureDiagramProps) {
  const edgesRef = useRef<SVGGElement | null>(null);

  const [mode, setMode] = useState<Mode>('overview');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [showArchitect, setShowArchitect] = useState(false);
  // Softens the Flow<->Sequence switch into a brief crossfade instead of an
  // instant hard swap, which read as an abrupt, unannounced jump.
  const [contentVisible, setContentVisible] = useState(true);

  useEffect(() => {
    setContentVisible(false);
    const t = setTimeout(() => setContentVisible(true), 30);
    return () => clearTimeout(t);
  }, [mode]);

  const selectedNode = useMemo(() => (selectedId ? NODES.find((n) => n.id === selectedId) ?? null : null), [selectedId]);

  // --- D3-owned subtree: draw edges via an imperative, keyed data-join. -----
  useEffect(() => {
    const g = edgesRef.current;
    if (!g) return;
    const gSel: Selection<SVGGElement, unknown, null, undefined> = select(g);

    gSel
      .selectAll<SVGPathElement, PhysicalEdge>('path.edge')
      .data(EDGES, (d) => d.id)
      .join((enter) => enter.append('path').attr('class', 'edge').attr('fill', 'none').attr('stroke-linecap', 'round'))
      .attr('d', (d) => edgeD(d, NODES))
      .attr('stroke-width', 2.5)
      .attr('stroke', C.edge)
      .attr('stroke-opacity', 0.55);

    return () => {
      gSel.selectAll('path.edge').remove();
    };
    // `mode` is a real dependency, not a lint-appeasing add: the <g> this
    // effect draws into lives inside the Flow-only branch of the mode
    // ternary, so it fully unmounts when switching to Sequence and a BRAND
    // NEW <g> mounts when switching back. An empty dep array only ran this
    // join once for the component's whole lifetime, so the second and later
    // times you returned to Flow, the fresh <g> never got repopulated and
    // every edge silently vanished.
  }, [mode]);

  // --- Hover/select highlight — pure attr update, no re-join. ---------------
  // Kill Switch has no edges of its own, so selecting it doesn't fall out of
  // the generic "edges touching the active node" rule below. Instead it's a
  // special case: it visualizes WHAT gets cut — the AI's reach into every
  // business domain — by forcing all four of those edges into a red, dashed
  // "severed" state.
  useEffect(() => {
    const g = edgesRef.current;
    if (!g) return;
    const activeNode = hoveredId ?? selectedId;
    const killSwitchActive = selectedId === 'killswitch';

    select(g)
      .selectAll<SVGPathElement, PhysicalEdge>('path.edge')
      .attr('stroke', (d) =>
        killSwitchActive && BUSINESS_EDGE_IDS.includes(d.id)
          ? C.deny
          : activeNode && (d.source === activeNode || d.target === activeNode)
          ? C.edgeActive
          : C.edge
      )
      .attr('stroke-opacity', (d) =>
        killSwitchActive && BUSINESS_EDGE_IDS.includes(d.id)
          ? 1
          : activeNode && (d.source === activeNode || d.target === activeNode)
          ? 0.95
          : 0.4
      )
      .attr('stroke-width', (d) =>
        killSwitchActive && BUSINESS_EDGE_IDS.includes(d.id)
          ? 3.5
          : activeNode && (d.source === activeNode || d.target === activeNode)
          ? 3.5
          : 2.5
      )
      .attr('stroke-dasharray', (d) => (killSwitchActive && BUSINESS_EDGE_IDS.includes(d.id) ? '7 5' : 'none'));
  }, [hoveredId, selectedId]);

  return (
    <div className="w-full rounded-2xl bg-[#0d0d14] border border-white/10 overflow-hidden shadow-2xl">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold text-slate-100">{title}</div>
          {mode === 'overview' && (
            <div className="hidden sm:block text-xs text-slate-500">hover to trace · click a node for detail</div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-black/30 border border-white/10 p-0.5 text-xs">
            {(['overview', 'flow'] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-md font-medium transition ${
                  mode === m ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {m === 'overview' ? 'Flow' : 'Sequence'}
              </button>
            ))}
          </div>

          {mode === 'overview' && (
            <label className="flex items-center gap-1.5 text-[11px] text-slate-400 cursor-pointer select-none">
              <input type="checkbox" checked={showArchitect} onChange={(e) => setShowArchitect(e.target.checked)} className="accent-orange-500" />
              For architects
            </label>
          )}
        </div>
      </div>

      <div
        className="transition-opacity duration-300 ease-out"
        style={{ opacity: contentVisible ? 1 : 0 }}
      >
      {mode === 'flow' ? (
        <div className="p-0">
          <SequenceDiagram />
        </div>
      ) : (
        <>
          <div className="px-5 py-2.5 border-b border-white/10 bg-black/20">
            <button
              onClick={() => setMode('flow')}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 transition"
            >
              ▶ See it as a Sequence
            </button>
          </div>

          <div className="flex flex-col lg:flex-row">
            <div className="flex-1 min-w-0">
              <svg
                viewBox={`-24 -24 ${VIEW_W + 48} ${VIEW_H + 48}`}
                preserveAspectRatio="xMidYMid meet"
                className="w-full h-auto block"
                role="img"
                aria-label="Interactive system architecture diagram"
              >
                <g ref={edgesRef} />

                {/* Resting-state edge labels, each offset along its edge's
                    perpendicular normal and backed by a pill so it stays
                    legible over any edge or glow. */}
                {EDGES.map((e) => {
                  const isKillCut = selectedId === 'killswitch' && BUSINESS_EDGE_IDS.includes(e.id);
                  // All four business edges turn red/dashed (see the D3
                  // highlight effect above), but they share a trunk, so
                  // only one of them renders the "access cut" text itself
                  // -- otherwise four labels stack exactly on top of each
                  // other where the trunk splits.
                  const label = isKillCut ? (e.id === 'ai_pricing' ? 'access cut' : null) : EDGE_LABELS[e.id];
                  if (!label) return null;
                  const detached = EDGE_LABEL_DETACHED[e.id];
                  const pillW = label.length * 5.6 + 8;

                  if (detached) {
                    return (
                      <g key={`lbl-${e.id}`} className="pointer-events-none select-none">
                        <line
                          x1={detached.x}
                          y1={detached.y + 9}
                          x2={detached.anchorX}
                          y2={detached.anchorY - 8}
                          stroke={C.textDim}
                          strokeOpacity={0.45}
                          strokeWidth={1.5}
                        />
                        <polygon
                          points={`${detached.anchorX - 4},${detached.anchorY - 8} ${detached.anchorX + 4},${detached.anchorY - 8} ${detached.anchorX},${detached.anchorY - 1}`}
                          fill={C.textDim}
                          fillOpacity={0.45}
                        />
                        <rect x={detached.x - pillW / 2} y={detached.y - 9} width={pillW} height={18} rx={9} fill="#0d0d14" fillOpacity={0.82} />
                        <text x={detached.x} y={detached.y + 3.5} textAnchor="middle" fontSize={10.5} fill={C.textDim}>
                          {label}
                        </text>
                      </g>
                    );
                  }

                  const [lx, ly] = edgeLabelAnchor(e, NODES, EDGE_LABEL_OFFSET[e.id] ?? 0, EDGE_LABEL_U[e.id] ?? 0.5);
                  return (
                    <g key={`lbl-${e.id}`} className="pointer-events-none select-none">
                      <rect
                        x={lx - pillW / 2}
                        y={ly - 9}
                        width={pillW}
                        height={18}
                        rx={9}
                        fill={isKillCut ? '#3a0f0f' : '#0d0d14'}
                        fillOpacity={0.82}
                        stroke={isKillCut ? C.deny : 'none'}
                        strokeOpacity={0.6}
                      />
                      <text x={lx} y={ly + 3.5} textAnchor="middle" fontSize={10.5} fontWeight={isKillCut ? 700 : 400} fill={isKillCut ? C.deny : C.textDim}>
                        {label}
                      </text>
                    </g>
                  );
                })}

                {/* Governance rail — a faint band threading the trust tier
                    (Okta → Access Rules → Approval Gate), reminding the
                    viewer these three checks are one connected governance
                    layer. */}
                <path
                  d="M 560 155 C 600 210, 610 235, 610 265 S 606 400, 604 473"
                  fill="none"
                  stroke="#ffd166"
                  strokeOpacity={0.16}
                  strokeWidth={3}
                  strokeDasharray="2 6"
                />

                {/* Nodes. */}
                {NODES.map((n) => {
                  const isSelected = n.id === selectedId;
                  const isHovered = n.id === hoveredId;
                  // Kill Switch has no edges of its own (see the highlight effect
                  // above), so its "victims" — the AI Agent and the four business
                  // domain boxes the red cut lines actually connect — need to be
                  // explicitly lit up here too. Otherwise selecting Kill Switch
                  // dims everything else on the canvas, including the very nodes
                  // the whole point is to draw attention to.
                  const isKillEndpoint = selectedId === 'killswitch' && (n.id === 'ai' || BUSINESS_NODE_IDS.includes(n.id));
                  const isActive = isSelected || isHovered || isKillEndpoint;
                  const dim = (hoveredId ?? selectedId) && !isActive;
                  const label = n.sublabel;

                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x},${n.y})`}
                      className="cursor-pointer"
                      opacity={n.dim && !isActive ? 0.6 : dim ? 0.55 : 1}
                      onMouseEnter={() => setHoveredId(n.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      onClick={() => setSelectedId((cur) => (cur === n.id ? null : n.id))}
                      style={{ transition: 'opacity 150ms ease' }}
                    >
                      <rect
                        x={-n.w / 2}
                        y={-n.h / 2}
                        width={n.w}
                        height={n.h}
                        rx={n.chip ? n.h / 2 : 12}
                        fill={n.chip ? 'rgba(0,0,0,0.35)' : C.nodeFill}
                        stroke={isKillEndpoint ? C.deny : n.accent}
                        strokeWidth={isSelected ? 3 : isKillEndpoint ? 2.5 : n.hero ? 2.5 : 1.5}
                        style={{
                          filter: isActive
                            ? `drop-shadow(0 0 ${n.hero || isKillEndpoint ? 16 : 10}px ${isKillEndpoint ? C.deny : n.accent}aa)`
                            : n.hero
                            ? `drop-shadow(0 0 8px ${n.accent}55)`
                            : 'none',
                          transition: 'stroke-width 120ms ease, filter 200ms ease',
                        }}
                      />
                      <text textAnchor="middle" y={n.chip ? 4 : -4} fontSize={n.chip ? 11 : n.hero ? 16 : 14} fontWeight={600} fill={C.text} className="select-none">
                        {n.label}
                      </text>
                      {!n.chip && (
                        <text textAnchor="middle" y={15} fontSize={10.5} fill={C.textDim} className="select-none">
                          {label}
                        </text>
                      )}
                      {n.order !== undefined && (
                        <g transform={`translate(${-n.w / 2 + 2},${-n.h / 2 + 2})`}>
                          <circle r={10} fill="#0b1120" stroke={n.accent} strokeWidth={1.5} />
                          <text textAnchor="middle" y={4} fontSize={11} fontWeight={700} fill="#fff" className="select-none">
                            {n.order}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>

            {/* Detail side panel */}
            <div className="lg:w-64 shrink-0 border-t lg:border-t-0 lg:border-l border-white/10 p-4">
              {selectedNode ? (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedNode.accent }} />
                    <span className="text-sm text-slate-100 font-semibold">{selectedNode.label}</span>
                  </div>
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">{selectedNode.sublabel}</div>
                  <p className="text-xs text-slate-300 leading-relaxed">{selectedNode.detail.body}</p>

                  {selectedNode.detail.subpoints && (
                    <ul className="mt-2 space-y-1">
                      {selectedNode.detail.subpoints.map((s, i) => (
                        <li key={i} className="text-[11px] text-slate-400 flex gap-1.5">
                          <span className="text-slate-600">—</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  )}

                  {selectedNode.detail.callouts && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {selectedNode.detail.callouts.map((c, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 rounded-full text-[9px] font-medium border"
                          style={{ color: selectedNode.accent, borderColor: `${selectedNode.accent}55`, backgroundColor: `${selectedNode.accent}15` }}
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  )}

                  {showArchitect && selectedNode.detail.architect && (
                    <div className="mt-3 pt-2 border-t border-white/10">
                      <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">For architects</div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">{selectedNode.detail.architect}</p>
                      {selectedNode.detail.tokenExample && (
                        <div className="mt-2.5">
                          <div className="text-[9.5px] text-slate-500 mb-1">{selectedNode.detail.tokenExample.label}</div>
                          <pre className="text-[9.5px] text-emerald-300/90 bg-black/40 border border-white/10 rounded-lg p-2 leading-snug whitespace-pre-wrap break-all">
                            {selectedNode.detail.tokenExample.json}
                          </pre>
                          <div className="text-[9px] text-slate-600 mt-1">Illustrative example — not a real token.</div>
                        </div>
                      )}
                    </div>
                  )}

                  <button onClick={() => setSelectedId(null)} className="mt-3 block text-[11px] text-slate-400 hover:text-slate-200 transition">
                    Clear selection
                  </button>
                </div>
              ) : (
                <div className="text-xs text-slate-500">
                  Select a node to see what it does. Hover any node to trace its connections, or hit "See it as a
                  Sequence" to see a real request move through the whole system step by step.
                </div>
              )}
            </div>
          </div>
        </>
      )}
      </div>
    </div>
  );
}
