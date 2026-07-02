'use client';

/**
 * D3ArchitectureDiagram — the customer-facing "how it works" experience.
 *
 * Pattern: HYBRID (verified against this app's real strict-mode tsconfig).
 * React owns all state, the SVG element, and every node/label as JSX so
 * click/hover stay native-React and drive the side panel + highlight state.
 * D3 owns only the interior of one <g ref> — the edge paths — via a keyed
 * data-join in useEffect, plus imperative attr mutation for hover-highlight
 * and the animated request packet's cx/cy. D3 never touches the DOM during
 * SSR; everything DOM-facing lives in effects that run client-side post-mount.
 *
 * Layout is FIXED (authored x/y), not d3-force — a small, known graph reads
 * as a stable story every load, which is the whole point of a pedagogical
 * diagram, and it makes the "watch a request" packet animation deterministic.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { select, type Selection } from 'd3-selection';
import { line, curveBumpX } from 'd3-shape';
import { easeCubicInOut } from 'd3-ease';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Persona = 'sarah' | 'mike';
type Mode = 'overview' | 'flow';
type ScenarioKey = 'happy' | 'denied' | 'vacation' | 'approval';

interface NodeDetail {
  body: string;
  subpoints?: string[];
  callouts?: string[];
  architect?: string;
}

interface BusinessChild {
  label: string;
  sublabel: string;
  body: string;
}

interface DiagramNode {
  id: string;
  label: string;
  sublabel: string | Record<Persona, string>;
  x: number;
  y: number;
  w: number;
  h: number;
  accent: string;
  hero?: boolean;
  dim?: boolean;
  chip?: boolean;
  description: string;
  detail: NodeDetail;
  children?: BusinessChild[];
}

interface PhysicalEdge {
  id: string;
  source: string;
  target: string;
}

type StepKind = 'move' | 'pulse' | 'audit' | 'hold';
type Outcome = 'deny' | 'approve' | 'reject';

interface FlowStep {
  kind: StepKind;
  edgeId?: string;
  reverse?: boolean;
  caption?: string; // omit to keep the previous caption on screen ("sticky")
  outcome?: Outcome;
  denyLabel?: string;
  pulseNodeIds?: string[];
  highlightChild?: string;
  contextChip?: string; // e.g. "on_vacation: true" — flashed near the FGA node
  auditDeny?: boolean; // tint the audit pulse red instead of the normal gold
}

interface Scenario {
  key: ScenarioKey;
  label: string;
  persona: Persona;
  question: string;
  steps: FlowStep[];
  closingLine: string;
  branches?: { approve: FlowStep[]; reject: FlowStep[] };
}

// ---------------------------------------------------------------------------
// Brand palette — mirrors tailwind.config.js so SVG fills match the app.
// Color = meaning: blue = Okta/identity, orange = access/action + the
// active packet, purple = human/governance, green = business data (reached
// only after checks pass), red-dashed = a denial, and ONLY a denial.
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
// Data model — Part 1/2 of the spec (9 nodes, 3 tiers; 8 physical edges
// carrying 15 labeled logical events, per the designer's own note that E3/E4
// and E6/E7 are two sequential events on one shared corridor).
// ---------------------------------------------------------------------------

const NODES: DiagramNode[] = [
  {
    id: 'you',
    label: 'You',
    sublabel: { sarah: 'Signed in as Sarah', mike: 'Signed in as Mike' },
    x: 76, y: 320, w: 116, h: 60,
    accent: C.purple,
    description: 'The signed-in person asking a question in plain English.',
    detail: {
      body: "This is the human driving the conversation. When you sign in, Okta confirms who you are and hands your session a verified identity badge. Everything the AI does next is done on your behalf and within your limits, never with its own free-standing power.",
      callouts: ['Verified by Okta login', 'Role: Sales (Sarah) / Warehouse (Mike)'],
    },
  },
  {
    id: 'ai',
    label: 'AI Assistant',
    sublabel: 'Understands + routes',
    x: 300, y: 320, w: 130, h: 60,
    accent: C.oktaBlue,
    description: 'The chatbot that understands your request and figures out which systems it needs.',
    detail: {
      body: "The assistant reads your question and decides which business systems could answer it. Important: it only routes and phrases. It never decides what you're allowed to see. That decision is made by Okta and the governance layer, not by the AI. So even a confused or manipulated AI cannot hand out data you aren't cleared for.",
      callouts: ['Has its own Okta identity (a Workload Principal)', 'No standing access of its own'],
      architect: 'The AI is powered by a language model (Claude, via the raw Anthropic SDK) for wording and routing only. It is not the security boundary.',
    },
  },
  {
    id: 'okta',
    label: 'Okta',
    sublabel: 'Identity + Access',
    x: 560, y: 120, w: 150, h: 74,
    accent: C.oktaBlue,
    hero: true,
    description: 'Issues a short-lived, single-purpose pass every time the AI needs to touch a system.',
    detail: {
      body: "Before the AI can reach any system, it must ask Okta for permission. Okta checks two things: who you are and whether your role is allowed to do this specific thing. If yes, Okta issues a short-lived pass that works for one system and one purpose only. If your role isn't allowed, Okta refuses and nothing is issued.",
      subpoints: [
        "Every system has its own separate pass. A pass for pricing can't open inventory.",
        'Passes expire in minutes, so a leaked one is near-worthless.',
        'The AI never holds a master key. It gets a fresh, narrow pass each time.',
      ],
      callouts: ['Passes are scoped per system + per action', "All-or-nothing: if a role can't do it, the whole request is refused"],
      architect: 'Under the hood this is a two-step token exchange (ID-JAG). Step 1 trades your login token for an assertion that names both you and the agent. Step 2 trades that for a scoped access token at a per-domain Authorization Server (api://progear-sales, -inventory, -customer, -pricing). Okta does not down-scope: if any requested scope is not grantable for your role, the entire exchange returns access_denied.',
    },
  },
  {
    id: 'fga',
    label: 'Access Rules',
    sublabel: 'Relationship + context check',
    x: 610, y: 300, w: 150, h: 70,
    accent: C.accent,
    hero: true,
    description: 'A live check of your relationships and current context, like whether you manage this warehouse or are on vacation.',
    detail: {
      body: "Roles alone aren't always enough. This layer answers the human questions: do you actually manage this warehouse? Is your clearance high enough? Are you on vacation right now? It checks live relationships and real-time context, not just a static job title. If your situation doesn't fit, access is blocked instantly, even if your role would normally allow it.",
      subpoints: [
        'Relationship: are you the manager or an approved viewer of this specific warehouse?',
        'Clearance: higher clearance automatically includes everything below it.',
        "Context: a live flag (for example 'on vacation') can block access this second, with no code change.",
      ],
      callouts: ['Blocks instantly on context change', 'No redeploy needed to revoke'],
      architect: "This is Auth0 FGA (Fine-Grained Authorization), a Zanzibar-style relationship graph with a clearance-level hierarchy (1-10, higher includes lower) and contextual tuples passed per-request (not stored) for things like 'on vacation'.",
    },
  },
  {
    id: 'approval',
    label: 'Approval Gate',
    sublabel: 'Human sign-off on big changes',
    x: 600, y: 505, w: 150, h: 64,
    accent: C.purple,
    description: 'High-impact actions (like a large inventory change) pause here for a human to approve.',
    detail: {
      body: "Some actions are too consequential to auto-approve. When the AI tries to make a large change, for example writing a big inventory adjustment, the request pauses and a real person is asked to approve or deny it. The AI cannot push it through on its own. Once approved, the action completes automatically.",
      subpoints: [
        'Triggered by impact (for example a large write quantity), not by every action.',
        'A named human approves or denies. Fully audited.',
        'Nothing happens to the business system until sign-off lands.',
      ],
      callouts: ['Human-in-the-loop', 'Auto-resumes once approved'],
      architect: 'This is a real Okta Identity Governance (OIG) Access Request. A background poller resumes the pending write once the request is approved in Okta.',
    },
  },
  {
    id: 'business',
    label: 'Business Systems',
    sublabel: '4 domains',
    x: 945, y: 400, w: 130, h: 66,
    accent: C.green,
    description: 'Your real company systems: inventory, pricing, customers, and sales.',
    detail: {
      body: "These are the real systems the assistant can draw on. Each one is protected separately and requires its own pass from Okta. The AI can only reach the ones your role and situation permit for the question you asked.",
    },
    children: [
      { label: 'Inventory', sublabel: 'read / write / alerts', body: 'Stock levels and adjustments. Reading is broadly allowed; large writes need approval and a manager relationship.' },
      { label: 'Pricing', sublabel: 'read', body: 'Product and deal pricing.' },
      { label: 'Customers', sublabel: 'read', body: 'Customer accounts and history.' },
      { label: 'Sales', sublabel: 'read', body: 'Orders, quotes, and pipeline.' },
    ],
  },
  {
    id: 'audit',
    label: 'Audit Trail',
    sublabel: 'Every decision logged',
    x: 762, y: 120, w: 132, h: 44,
    accent: C.slate,
    dim: true,
    description: 'A permanent, searchable record of every pass issued and every allow/deny decision.',
    detail: {
      body: "Every single access decision, granted or denied, is written to a tamper-evident log the moment it happens. Security and compliance teams can answer 'who accessed what, when, and why' for any request the AI ever made, without trusting the AI to self-report.",
      callouts: ['Queryable', 'Covers grants AND denials'],
      architect: "This is Okta's System Log — a queryable, tamper-evident event stream.",
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
      body: "If anything looks wrong, an admin can cut the AI's access in one step: deactivate its identity in Okta, or flip a context flag in the access rules. Because every pass is short-lived and re-issued each time, revocation takes effect almost immediately. No code change, no redeploy.",
      callouts: ['Deactivate identity — OR — flip a context flag'],
    },
  },
];

const HUMAN_NODE: DiagramNode = {
  id: 'human',
  label: 'Approver',
  sublabel: 'A named person',
  x: 945, y: 558, w: 120, h: 52,
  accent: C.purple,
  description: 'The real person who reviews high-impact requests.',
  detail: { body: 'A named human in Okta Identity Governance reviews the request and approves or denies it. The AI cannot bypass this step.' },
};

const EDGES: PhysicalEdge[] = [
  { id: 'you_ai', source: 'you', target: 'ai' },
  { id: 'ai_okta', source: 'ai', target: 'okta' },
  { id: 'ai_fga', source: 'ai', target: 'fga' },
  { id: 'ai_approval', source: 'ai', target: 'approval' },
  { id: 'approval_human', source: 'approval', target: 'human' },
  { id: 'ai_business', source: 'ai', target: 'business' },
  { id: 'okta_audit', source: 'okta', target: 'audit' },
  { id: 'fga_audit', source: 'fga', target: 'audit' },
];

// ---------------------------------------------------------------------------
// Part 3/4 of the spec — happy path + the three first-class denial variants.
// ---------------------------------------------------------------------------

const SCENARIOS: Record<ScenarioKey, Scenario> = {
  happy: {
    key: 'happy',
    label: 'Happy path',
    persona: 'sarah',
    question: 'How many climbing helmets do we have in stock?',
    steps: [
      { kind: 'move', edgeId: 'you_ai', caption: 'Sarah asks the assistant a question in plain English.' },
      { kind: 'pulse', pulseNodeIds: ['ai'], caption: "The assistant works out which systems could answer, but it can't touch them yet." },
      { kind: 'move', edgeId: 'ai_okta', caption: "Before touching anything, the assistant asks Okta for permission, on Sarah's behalf." },
      { kind: 'pulse', pulseNodeIds: ['okta'], caption: "Okta confirms it's really Sarah, and that her role is allowed to do this." },
      { kind: 'move', edgeId: 'ai_okta', reverse: true, caption: 'Okta issues a short-lived pass, good for one system and one purpose only.' },
      { kind: 'move', edgeId: 'ai_fga' },
      { kind: 'move', edgeId: 'ai_fga', reverse: true, caption: "The access rules confirm Sarah's relationships and current context are fine." },
      { kind: 'audit', caption: 'Every decision so far is written to a permanent audit log.' },
      { kind: 'move', edgeId: 'ai_business', highlightChild: 'Inventory', caption: 'Now, and only now, the assistant reaches the inventory system, using the narrow pass.' },
      { kind: 'move', edgeId: 'ai_business', reverse: true, caption: 'Inventory returns just the stock data Sarah is cleared to see.' },
      { kind: 'move', edgeId: 'you_ai', reverse: true, caption: 'Sarah gets a clear answer, and the AI never had more power than she does.' },
    ],
    closingLine: 'Same pattern every time: verify the person, issue a narrow pass, check context, log it, then act.',
  },
  denied: {
    key: 'denied',
    label: 'Access denied',
    persona: 'sarah',
    question: 'Set climbing-helmet stock to 500.',
    steps: [
      { kind: 'move', edgeId: 'you_ai', caption: 'Sarah asks the assistant to change inventory: "Set climbing-helmet stock to 500."' },
      { kind: 'pulse', pulseNodeIds: ['ai'], caption: "The assistant works out which systems could answer, but it can't touch them yet." },
      { kind: 'move', edgeId: 'ai_okta', caption: "Before touching anything, the assistant asks Okta for permission, on Sarah's behalf." },
      { kind: 'pulse', pulseNodeIds: ['okta'], caption: "Sarah's role can read inventory but not change it." },
      { kind: 'move', edgeId: 'ai_okta', reverse: true, outcome: 'deny', denyLabel: 'role not allowed — refused', caption: 'Okta refuses to issue the pass. The whole request is stopped.' },
      { kind: 'audit', auditDeny: true, caption: 'The inventory system was never even contacted. Nothing leaked.' },
    ],
    closingLine: "The AI asked. Okta said no. That's the point.",
  },
  vacation: {
    key: 'vacation',
    label: 'Blocked on vacation',
    persona: 'mike',
    question: "Add 200 units to my warehouse's stock.",
    steps: [
      { kind: 'move', edgeId: 'you_ai', caption: "Mike, a warehouse manager, asks to adjust his warehouse's stock." },
      { kind: 'pulse', pulseNodeIds: ['ai'], caption: "The assistant works out which systems could answer, but it can't touch them yet." },
      { kind: 'move', edgeId: 'ai_okta', caption: "The assistant asks Okta for permission, on Mike's behalf." },
      { kind: 'pulse', pulseNodeIds: ['okta'], caption: "Okta confirms Mike's identity and role." },
      { kind: 'move', edgeId: 'ai_okta', reverse: true, caption: "Mike's role and manager relationship both check out, so Okta issues the pass." },
      { kind: 'move', edgeId: 'ai_fga', caption: "The assistant checks the live access rules for Mike's warehouse." },
      { kind: 'move', edgeId: 'ai_fga', reverse: true, outcome: 'deny', denyLabel: 'on vacation — blocked', contextChip: 'on_vacation: true', caption: 'But the access rules see a live flag: Mike is on vacation right now.' },
      { kind: 'audit', auditDeny: true, caption: 'Access is blocked this second. No code change was needed to enforce it.' },
    ],
    closingLine: "Even a legitimate manager is blocked the instant context changes. Flip the flag back and he's in again.",
  },
  approval: {
    key: 'approval',
    label: 'Needs approval',
    persona: 'mike',
    question: 'Add 10,000 units to warehouse stock.',
    steps: [
      { kind: 'move', edgeId: 'you_ai', caption: 'Mike asks to add a large amount of stock: 10,000 units.' },
      { kind: 'pulse', pulseNodeIds: ['ai'], caption: "The assistant works out which systems could answer, but it can't touch them yet." },
      { kind: 'move', edgeId: 'ai_okta', caption: "The assistant asks Okta for permission, on Mike's behalf." },
      { kind: 'pulse', pulseNodeIds: ['okta'], caption: "Okta confirms Mike's role and manager relationship are valid." },
      { kind: 'move', edgeId: 'ai_okta', reverse: true, caption: 'Okta issues a scoped pass for warehouse writes.' },
      { kind: 'move', edgeId: 'ai_fga' },
      { kind: 'move', edgeId: 'ai_fga', reverse: true, caption: "The access rules confirm Mike isn't on vacation right now, so context checks out too." },
      { kind: 'move', edgeId: 'ai_approval', pulseNodeIds: ['approval'], caption: 'This change is big enough to require a human sign-off.' },
      { kind: 'hold', edgeId: 'approval_human', caption: 'The request pauses. A named person is asked to approve or deny.' },
    ],
    closingLine: '',
    branches: {
      approve: [
        { kind: 'move', edgeId: 'approval_human', reverse: true, caption: 'Approved. Now, and only now, the large change is written.' },
        { kind: 'move', edgeId: 'ai_business', highlightChild: 'Inventory', caption: 'The assistant writes the 10,000-unit adjustment.' },
        { kind: 'move', edgeId: 'ai_business', reverse: true, caption: 'Inventory confirms the update.' },
        { kind: 'move', edgeId: 'you_ai', reverse: true, caption: 'Mike gets confirmation that his 10,000-unit adjustment went through.' },
      ],
      reject: [
        { kind: 'move', edgeId: 'approval_human', reverse: true, outcome: 'deny', denyLabel: 'denied by approver', caption: 'A human denied it. The AI could not push it through on its own.' },
        { kind: 'audit', auditDeny: true, caption: 'The denial, like every decision, is fully logged.' },
      ],
    },
  },
};

const SCENARIO_ORDER: ScenarioKey[] = ['happy', 'denied', 'vacation', 'approval'];

const APPROVE_CLOSING = 'For high-impact actions, a person stays in the loop. The AI proposes; a human disposes.';
const REJECT_CLOSING = 'A human stayed in the loop, and said no. The AI never got the chance to push the change through on its own.';

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

// A few edges are genuine multi-point bent paths, not straight two-point curves.
// ai_business arcs DOWN out of the AI hub and through the open lane between the
// FGA box (bottom y=335) and the Approval Gate (top y=473) — around y=400 — so
// its long reach to the resource tier never crosses the AI's other spokes nor
// the okta_audit / fga_audit edges. The interior waypoint sits in that gap.
// Points are authored source->target; pointAlongEdge handles reverse + the
// packet is arc-length parameterized so it tracks the full polyline at even
// speed (not linearly between just the two endpoints).
const EDGE_WAYPOINTS: Record<string, Array<[number, number]>> = {
  ai_business: [[470, 400]],
};

// Full ordered point list for an edge (source, ...waypoints, target).
function edgePoints(edge: PhysicalEdge, nodes: DiagramNode[]): Array<[number, number]> {
  const s = findNode(nodes, edge.source);
  const t = findNode(nodes, edge.target);
  const mids = EDGE_WAYPOINTS[edge.id] ?? [];
  return [[s.x, s.y], ...mids, [t.x, t.y]];
}

function edgeD(edge: PhysicalEdge, nodes: DiagramNode[]): string {
  return linkPath(edgePoints(edge, nodes))!;
}

// Position at fraction `u` (0..1) along the edge's full polyline, by cumulative
// arc length so the animated packet moves at a constant visual speed across a
// bent, multi-segment path. Straight two-point edges reduce to a plain lerp.
function pointAlongEdge(edge: PhysicalEdge, nodes: DiagramNode[], u: number, reverse?: boolean): [number, number] {
  const raw = edgePoints(edge, nodes);
  const pts = reverse ? [...raw].reverse() : raw;

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
      return [
        pts[i][0] + (pts[i + 1][0] - pts[i][0]) * local,
        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * local,
      ];
    }
    acc += segLens[i];
  }
  return [pts[pts.length - 1][0], pts[pts.length - 1][1]];
}

function sublabelFor(n: DiagramNode, persona: Persona): string {
  return typeof n.sublabel === 'string' ? n.sublabel : n.sublabel[persona];
}

// Resting-state edge labels (Overview mode only; the caption bar takes over
// once a scenario is playing).
const EDGE_LABELS: Record<string, string> = {
  you_ai: 'asks / answers',
  ai_okta: 'requests a pass ↔ issues one',
  ai_fga: 'checks context ↔ confirms',
  ai_approval: 'high-impact action',
  approval_human: 'needs sign-off',
  ai_business: 'uses the pass ↔ returns data',
  okta_audit: 'logs the decision',
  fga_audit: 'logs the check',
};

// Each label is pushed off its edge midpoint along the edge's perpendicular
// normal by this many px (signed: which side of the line). Tuned so the two
// corridors that both fan out from the AI node (ai_okta / ai_fga) sit on
// opposite sides and never share a vertical band, and so no anchor lands on a
// node. A semi-opaque pill is drawn behind each label at render time, so a
// label stays legible even if it happens to sit over an edge.
const EDGE_LABEL_OFFSET: Record<string, number> = {
  you_ai: -16,
  ai_okta: -12,
  ai_fga: 16,
  ai_approval: 18,
  approval_human: 16,
  ai_business: -20, // pushed ABOVE its low gap-lane so the pill clears the FGA box
  okta_audit: 50, // pushed BELOW the short horizontal Okta↔Audit edge (clears both boxes)
  fga_audit: -16,
};

// A few labels slide off the geometric midpoint toward one endpoint (u != 0.5)
// so their pill clears a nearby node. Only overrides listed here differ from 0.5.
const EDGE_LABEL_U: Record<string, number> = {
  you_ai: 0.484, // recenter "asks / answers" in the You↔AI gap so its pill clears both
};

// Anchor a label at fraction `u` along the edge's full polyline (arc-length
// parameterized, so bent edges anchor on the real path midpoint, not the
// straight chord), then push it off along the local tangent's perpendicular
// normal by `offset` px. Mirrors the geometry the verification script asserts.
function edgeLabelAnchor(edge: PhysicalEdge, nodes: DiagramNode[], offset: number, u = 0.5): [number, number] {
  const [px, py] = pointAlongEdge(edge, nodes, u);
  // Local tangent: sample a hair before/after u so the normal follows the bend.
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
  const packetRef = useRef<SVGCircleElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);
  const resolveHoldRef = useRef<((decision: 'approve' | 'reject') => void) | null>(null);

  const [mode, setMode] = useState<Mode>('overview');
  const [persona, setPersona] = useState<Persona>('sarah');
  const [scenarioKey, setScenarioKey] = useState<ScenarioKey>('happy');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [showArchitect, setShowArchitect] = useState(false);

  const [isFlowing, setIsFlowing] = useState(false);
  const [caption, setCaption] = useState<string>('Click "Play" to watch a real request move through the system.');
  const [awaitingDecision, setAwaitingDecision] = useState(false);
  const [deniedEdges, setDeniedEdges] = useState<Record<string, string>>({});
  const [pulsingIds, setPulsingIds] = useState<string[]>([]);
  const [highlightChild, setHighlightChild] = useState<string | null>(null);
  const [contextChip, setContextChip] = useState<string | null>(null);
  const [showHuman, setShowHuman] = useState(false);
  const [auditFlash, setAuditFlash] = useState<{ deny: boolean } | null>(null);

  const scenario = SCENARIOS[scenarioKey];

  const nodes = useMemo(() => (showHuman ? [...NODES, HUMAN_NODE] : NODES), [showHuman]);
  const edges = useMemo(
    () => (showHuman ? EDGES : EDGES.filter((e) => e.id !== 'approval_human')),
    [showHuman]
  );

  const selectedNode = useMemo(
    () => (selectedId ? nodes.find((n) => n.id === selectedId) ?? null : null),
    [selectedId, nodes]
  );

  // --- D3-owned subtree: draw edges via an imperative, keyed data-join. -----
  useEffect(() => {
    const g = edgesRef.current;
    if (!g) return;
    const gSel: Selection<SVGGElement, unknown, null, undefined> = select(g);

    gSel
      .selectAll<SVGPathElement, PhysicalEdge>('path.edge')
      .data(edges, (d) => d.id)
      .join((enter) =>
        enter.append('path').attr('class', 'edge').attr('fill', 'none').attr('stroke-linecap', 'round')
      )
      .attr('d', (d) => edgeD(d, nodes))
      .attr('stroke-width', 2.5)
      .attr('stroke', (d) => (deniedEdges[d.id] ? C.deny : C.edge))
      .attr('stroke-dasharray', (d) => (deniedEdges[d.id] ? '6 5' : 'none'))
      .attr('stroke-opacity', (d) => (deniedEdges[d.id] ? 0.9 : 0.55));

    // Keyed join is idempotent under StrictMode's dev double-invoke; cleanup
    // still clears on a genuine remount.
    return () => {
      gSel.selectAll('path.edge').remove();
    };
  }, [edges, nodes, deniedEdges]);

  // --- Hover/select highlight — pure attr update, no re-join. ---------------
  useEffect(() => {
    const g = edgesRef.current;
    if (!g) return;
    const activeNode = hoveredId ?? selectedId;

    select(g)
      .selectAll<SVGPathElement, PhysicalEdge>('path.edge')
      .attr('stroke', (d) => {
        if (deniedEdges[d.id]) return C.deny;
        const active = activeNode && (d.source === activeNode || d.target === activeNode);
        return active ? C.edgeActive : C.edge;
      })
      .attr('stroke-opacity', (d) => {
        if (deniedEdges[d.id]) return 0.9;
        const active = activeNode && (d.source === activeNode || d.target === activeNode);
        return active ? 0.95 : 0.4;
      })
      .attr('stroke-width', (d) => {
        const active = activeNode && (d.source === activeNode || d.target === activeNode);
        return active ? 3.5 : 2.5;
      });
  }, [hoveredId, selectedId, deniedEdges]);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // --- Packet movement along one edge, eased, cancellable. ------------------
  const movePacket = useCallback(
    (edgeId: string, reverse: boolean | undefined, deny: boolean) =>
      new Promise<void>((resolve) => {
        const edge = edges.find((e) => e.id === edgeId) ?? EDGES.find((e) => e.id === edgeId)!;
        const packet = packetRef.current;
        if (!packet) {
          resolve();
          return;
        }
        const perEdgeMs = 700;
        let start: number | null = null;

        const step = (ts: number) => {
          if (cancelledRef.current) {
            resolve();
            return;
          }
          if (start === null) start = ts;
          const raw = Math.min((ts - start) / perEdgeMs, 1);
          const u = easeCubicInOut(raw);
          const [px, py] = pointAlongEdge(edge, nodes, u, reverse);
          select(packet)
            .attr('cx', px)
            .attr('cy', py)
            .attr('opacity', 1)
            .attr('fill', deny && raw > 0.6 ? C.deny : C.accent);

          if (raw < 1) {
            rafRef.current = requestAnimationFrame(step);
          } else {
            setTimeout(() => {
              select(packet).attr('opacity', 0);
              resolve();
            }, deny ? 250 : 120);
          }
        };
        rafRef.current = requestAnimationFrame(step);
      }),
    [edges, nodes]
  );

  const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

  const runStep = useCallback(
    async (step: FlowStep) => {
      if (cancelledRef.current) return;
      if (step.caption) setCaption(step.caption);
      if (step.highlightChild) setHighlightChild(step.highlightChild);
      if (step.contextChip) setContextChip(step.contextChip);

      if (step.kind === 'pulse') {
        setPulsingIds(step.pulseNodeIds ?? []);
        await wait(600);
        setPulsingIds([]);
        return;
      }

      if (step.kind === 'audit') {
        setAuditFlash({ deny: !!step.auditDeny });
        setPulsingIds(['audit']);
        await wait(650);
        setAuditFlash(null);
        setPulsingIds([]);
        return;
      }

      if (step.kind === 'hold') {
        setShowHuman(true);
        await wait(50); // let the human node mount before the packet targets it
        await movePacket(step.edgeId!, false, false);
        setPulsingIds(['human', 'approval']);
        setAwaitingDecision(true);
        await new Promise<'approve' | 'reject'>((resolve) => {
          resolveHoldRef.current = resolve;
        });
        setAwaitingDecision(false);
        setPulsingIds([]);
        return;
      }

      // 'move'
      if (step.pulseNodeIds) setPulsingIds(step.pulseNodeIds);
      await movePacket(step.edgeId!, step.reverse, step.outcome === 'deny');
      if (step.outcome === 'deny' && step.edgeId) {
        setDeniedEdges((prev) => ({ ...prev, [step.edgeId!]: step.denyLabel ?? 'denied' }));
      }
      setPulsingIds([]);
    },
    [movePacket]
  );

  const runFlow = useCallback(async () => {
    if (isFlowing) return;
    cancelledRef.current = false;
    setIsFlowing(true);
    setDeniedEdges({});
    setHighlightChild(null);
    setContextChip(null);
    setShowHuman(false);
    setPersona(scenario.persona);

    for (const step of scenario.steps) {
      await runStep(step);
      if (cancelledRef.current) return;
    }

    if (!scenario.branches) {
      setCaption(scenario.closingLine);
      setIsFlowing(false);
    }
  }, [isFlowing, scenario, runStep]);

  const handleDecision = useCallback(
    async (decision: 'approve' | 'reject') => {
      if (!resolveHoldRef.current) return;
      resolveHoldRef.current(decision);
      resolveHoldRef.current = null;

      const branch = decision === 'approve' ? scenario.branches?.approve : scenario.branches?.reject;
      if (branch) {
        for (const step of branch) {
          await runStep(step);
          if (cancelledRef.current) return;
        }
      }
      setCaption(decision === 'approve' ? APPROVE_CLOSING : REJECT_CLOSING);
      setIsFlowing(false);
    },
    [scenario, runStep]
  );

  const handlePlay = () => {
    setMode('flow');
    void runFlow();
  };

  const handleScenarioChange = (key: ScenarioKey) => {
    if (isFlowing) return;
    setScenarioKey(key);
    setPersona(SCENARIOS[key].persona);
    setDeniedEdges({});
    setHighlightChild(null);
    setContextChip(null);
    setShowHuman(false);
    setCaption(`"${SCENARIOS[key].question}" — click Play to watch what happens.`);
  };

  return (
    <div className="w-full rounded-2xl bg-[#0d0d14] border border-white/10 overflow-hidden shadow-2xl">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold text-slate-100">{title}</div>
          <div className="hidden sm:block text-xs text-slate-500">hover to trace · click a node for detail</div>
        </div>

        <div className="flex items-center gap-2">
          {/* Identity switcher — the single highest-leverage interaction. */}
          <div className="flex rounded-lg bg-black/30 border border-white/10 p-0.5 text-xs">
            {(['sarah', 'mike'] as Persona[]).map((p) => (
              <button
                key={p}
                onClick={() => setPersona(p)}
                disabled={isFlowing}
                className={`px-3 py-1.5 rounded-md font-medium transition ${
                  persona === p ? 'bg-okta-blue text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {p === 'sarah' ? 'Sarah · Sales' : 'Mike · Warehouse'}
              </button>
            ))}
          </div>

          <div className="flex rounded-lg bg-black/30 border border-white/10 p-0.5 text-xs">
            {(['overview', 'flow'] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-md font-medium transition ${
                  mode === m ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {m === 'overview' ? 'Overview' : 'Watch a request'}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-1.5 text-[11px] text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showArchitect}
              onChange={(e) => setShowArchitect(e.target.checked)}
              className="accent-orange-500"
            />
            For architects
          </label>
        </div>
      </div>

      {/* Scenario picker — only meaningful in "Watch a request" mode. */}
      {mode === 'flow' && (
        <div className="flex flex-wrap items-center gap-2 px-5 py-2.5 border-b border-white/10 bg-black/20">
          <span className="text-[11px] text-slate-500 uppercase tracking-wide">Try a scenario</span>
          {SCENARIO_ORDER.map((k) => (
            <button
              key={k}
              onClick={() => handleScenarioChange(k)}
              disabled={isFlowing}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition disabled:opacity-50 ${
                scenarioKey === k
                  ? 'bg-orange-500/20 text-orange-300 border-orange-500/50'
                  : 'bg-white/5 text-slate-300 border-white/10 hover:border-white/25'
              }`}
            >
              {SCENARIOS[k].label}
            </button>
          ))}
          <button
            onClick={handlePlay}
            disabled={isFlowing}
            className="ml-auto px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {isFlowing ? 'Playing…' : '▶ Play'}
          </button>
        </div>
      )}
      {mode === 'overview' && (
        <div className="px-5 py-2.5 border-b border-white/10 bg-black/20">
          <button
            onClick={handlePlay}
            className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 transition"
          >
            ▶ Watch a request flow
          </button>
        </div>
      )}

      <div className="flex flex-col lg:flex-row">
        <div className="flex-1 min-w-0">
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            preserveAspectRatio="xMidYMid meet"
            className="w-full h-auto block"
            role="img"
            aria-label="Interactive system architecture diagram"
          >
            <g ref={edgesRef} />

            {/* Denial glyph + label at the midpoint of any currently-denied edge. */}
            {edges.map((e) => {
              if (!deniedEdges[e.id]) return null;
              const [mx, my] = pointAlongEdge(e, nodes, 0.5);
              return (
                <g key={`deny-${e.id}`} transform={`translate(${mx},${my})`}>
                  <circle r={10} fill="#1a0b0b" stroke={C.deny} strokeWidth={2} />
                  <line x1={-5} y1={5} x2={5} y2={-5} stroke={C.deny} strokeWidth={2} />
                  <text y={22} textAnchor="middle" fontSize={10} fill={C.deny} className="select-none font-medium">
                    {deniedEdges[e.id]}
                  </text>
                </g>
              );
            })}

            {/* Resting-state edge labels — Overview mode only. Each label is
                offset along its edge's perpendicular normal (so the two
                corridors fanning out of the AI node don't stack) and backed by
                a semi-opaque pill so it stays legible over any edge or glow. */}
            {!isFlowing &&
              mode === 'overview' &&
              edges.map((e) => {
                const label = EDGE_LABELS[e.id];
                if (!label) return null;
                const [lx, ly] = edgeLabelAnchor(e, nodes, EDGE_LABEL_OFFSET[e.id] ?? 0, EDGE_LABEL_U[e.id] ?? 0.5);
                const pillW = label.length * 5.6 + 8;
                return (
                  <g key={`lbl-${e.id}`} className="pointer-events-none select-none">
                    <rect
                      x={lx - pillW / 2}
                      y={ly - 9}
                      width={pillW}
                      height={18}
                      rx={9}
                      fill="#0d0d14"
                      fillOpacity={0.82}
                    />
                    <text x={lx} y={ly + 3.5} textAnchor="middle" fontSize={10.5} fill={C.textDim}>
                      {label}
                    </text>
                  </g>
                );
              })}

            {/* Governance rail — a faint band threading the trust tier
                (Okta → Access Rules → Approval Gate), reminding the viewer
                these three checks are one connected governance layer. Follows
                the trust column down: okta(560,120) → fga(610,300) → approval(600,505). */}
            <path
              d="M 560 157 C 600 210, 610 235, 610 265 S 606 400, 604 473"
              fill="none"
              stroke="#ffd166"
              strokeOpacity={0.16}
              strokeWidth={3}
              strokeDasharray="2 6"
            />

            {/* Context chip (vacation flag) flashed just above the FGA node. */}
            {contextChip && (
              <g transform="translate(610, 248)">
                <rect x={-62} y={-12} width={124} height={22} rx={11} fill="#3a0f0f" stroke={C.deny} strokeWidth={1.5} />
                <text textAnchor="middle" y={4} fontSize={10} fill={C.deny} fontFamily="monospace">
                  {contextChip}
                </text>
              </g>
            )}

            {/* Audit flash — ring around the Audit Trail node (now tucked
                right of Okta at 762,120). Sized to hug the node without
                reaching the Okta box to its left. */}
            {auditFlash && (
              <circle cx={762} cy={120} r={52} fill="none" stroke={auditFlash.deny ? C.deny : '#ffd166'} strokeWidth={2} opacity={0.4} />
            )}

            {/* Animated request packet. */}
            <circle
              ref={packetRef}
              r={7}
              fill={C.accent}
              opacity={0}
              className="pointer-events-none"
              style={{ filter: 'drop-shadow(0 0 6px rgba(255,107,53,0.9))' }}
            />

            {/* Nodes. */}
            {nodes.map((n) => {
              const isSelected = n.id === selectedId;
              const isHovered = n.id === hoveredId;
              const isPulsing = pulsingIds.includes(n.id);
              const dim = (hoveredId ?? selectedId) && !isSelected && !isHovered && !isPulsing;
              const label = sublabelFor(n, persona);

              return (
                <g
                  key={n.id}
                  transform={`translate(${n.x},${n.y})`}
                  className="cursor-pointer"
                  opacity={n.dim && !isSelected && !isHovered && !isPulsing ? 0.6 : dim ? 0.55 : 1}
                  onMouseEnter={() => setHoveredId(n.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => setSelectedId((cur) => (cur === n.id ? null : n.id))}
                  style={{ transition: 'opacity 150ms ease' }}
                >
                  {n.id === 'business' && (
                    <>
                      <rect x={-n.w / 2 + 6} y={-n.h / 2 + 8} width={n.w} height={n.h} rx={12} fill={C.nodeFill} stroke={n.accent} strokeOpacity={0.35} strokeWidth={1} />
                      <rect x={-n.w / 2 + 3} y={-n.h / 2 + 4} width={n.w} height={n.h} rx={12} fill={C.nodeFill} stroke={n.accent} strokeOpacity={0.6} strokeWidth={1} />
                    </>
                  )}

                  <rect
                    x={-n.w / 2}
                    y={-n.h / 2}
                    width={n.w}
                    height={n.h}
                    rx={n.chip ? n.h / 2 : 12}
                    fill={n.chip ? 'rgba(0,0,0,0.35)' : C.nodeFill}
                    stroke={n.accent}
                    strokeWidth={isSelected ? 3 : n.hero ? 2.5 : 1.5}
                    style={{
                      filter:
                        isSelected || isHovered || isPulsing
                          ? `drop-shadow(0 0 ${n.hero ? 16 : 10}px ${n.accent}${isPulsing ? 'ff' : 'aa'})`
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
                  {n.id === 'business' && highlightChild && (
                    <text textAnchor="middle" y={n.h / 2 + 16} fontSize={10} fill={C.accent} className="select-none font-medium">
                      → {highlightChild}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Caption bar */}
          <div className="px-5 py-3 border-t border-white/10 bg-black/20 min-h-[52px] flex items-center">
            <p className="text-sm text-slate-200 leading-snug">{caption}</p>
          </div>

          {/* Approve/Deny — the human-in-the-loop pause. */}
          {awaitingDecision && (
            <div className="px-5 py-3 border-t border-white/10 bg-purple-950/40 flex items-center gap-3">
              <span className="text-xs text-slate-300">Awaiting a human decision:</span>
              <button onClick={() => handleDecision('approve')} className="px-3 py-1.5 rounded-md text-xs font-semibold bg-green-600/80 hover:bg-green-600 text-white transition">
                Approve
              </button>
              <button onClick={() => handleDecision('reject')} className="px-3 py-1.5 rounded-md text-xs font-semibold bg-red-600/80 hover:bg-red-600 text-white transition">
                Deny
              </button>
            </div>
          )}
        </div>

        {/* Detail side panel */}
        <div className="lg:w-80 shrink-0 border-t lg:border-t-0 lg:border-l border-white/10 p-5">
          {selectedNode ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedNode.accent }} />
                <span className="text-slate-100 font-semibold">{selectedNode.label}</span>
              </div>
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">{sublabelFor(selectedNode, persona)}</div>
              <p className="text-sm text-slate-300 leading-relaxed">{selectedNode.detail.body}</p>

              {selectedNode.detail.subpoints && (
                <ul className="mt-3 space-y-1.5">
                  {selectedNode.detail.subpoints.map((s, i) => (
                    <li key={i} className="text-xs text-slate-400 flex gap-2">
                      <span className="text-slate-600">—</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              )}

              {selectedNode.detail.callouts && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {selectedNode.detail.callouts.map((c, i) => (
                    <span
                      key={i}
                      className="px-2 py-1 rounded-full text-[10px] font-medium border"
                      style={{ color: selectedNode.accent, borderColor: `${selectedNode.accent}55`, backgroundColor: `${selectedNode.accent}15` }}
                    >
                      {c}
                    </span>
                  ))}
                </div>
              )}

              {selectedNode.children && (
                <div className="mt-4 space-y-2">
                  {selectedNode.children.map((c) => (
                    <div
                      key={c.label}
                      className={`rounded-lg border p-2.5 transition ${
                        highlightChild === c.label ? 'border-orange-500/60 bg-orange-500/10' : 'border-white/10 bg-white/[0.02]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-200">{c.label}</span>
                        <span className="text-[10px] text-slate-500">{c.sublabel}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1">{c.body}</p>
                    </div>
                  ))}
                </div>
              )}

              {showArchitect && selectedNode.detail.architect && (
                <div className="mt-4 pt-3 border-t border-white/10">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">For architects</div>
                  <p className="text-xs text-slate-400 leading-relaxed">{selectedNode.detail.architect}</p>
                </div>
              )}

              {selectedNode.id === 'you' && (
                <button
                  onClick={() => setPersona((p) => (p === 'sarah' ? 'mike' : 'sarah'))}
                  className="mt-4 text-xs text-orange-400 hover:text-orange-300 transition"
                >
                  See the difference → switch to {persona === 'sarah' ? 'Mike' : 'Sarah'}
                </button>
              )}

              <button onClick={() => setSelectedId(null)} className="mt-4 block text-xs text-slate-400 hover:text-slate-200 transition">
                Clear selection
              </button>
            </div>
          ) : (
            <div className="text-sm text-slate-500">
              Select a node to see what it does. Hover any node to trace its connections, or hit Play to watch a real
              request move through the whole system.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
