'use client';

/**
 * SequenceDiagram — the "Watch a request" experience.
 *
 * Replaces an earlier hub-and-spoke-graph-plus-animated-dot design that
 * repeated feedback confirmed doesn't work: a dot moving along an arbitrary
 * edge on a free-floating graph gives no stable "forward" direction, no
 * fixed sense of which actor is which, and no persistent notion of "where
 * are we in the story" — the literal "can't connect the dots" complaint.
 *
 * This is a UML-style sequence diagram instead: each actor gets a FIXED
 * vertical lane; each step is a discrete, numbered, horizontal arrow
 * stacked strictly top-to-bottom, so "down" always means "later". Exactly
 * one step is active at a time — its arrow draws itself and both lanes it
 * touches glow — with played steps left as dimmed breadcrumbs above and
 * future steps ghosted below. A persistent "Step N of M" counter plus a
 * scrubber removes any ambiguity about position in the sequence.
 *
 * Same hybrid pattern as the Overview diagram: React owns state, the SVG,
 * and every row as JSX; D3 owns only the imperative self-drawing stroke
 * animation of the single active arrow (stroke-dashoffset).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { select } from 'd3-selection';
import { easeCubicInOut } from 'd3-ease';

type Persona = 'sarah' | 'mike';
type MsgKind = 'call' | 'return' | 'self' | 'deny' | 'approvalPause';

const C = {
  oktaBlue: '#007dc1',
  accent: '#ff6b35',
  purple: '#8b5cf6',
  green: '#22c55e',
  deny: '#ef4444',
  lane: '#475569',
  laneActive: '#ff6b35',
  nodeFill: '#16213e',
  text: '#e2e8f0',
  textDim: '#94a3b8',
} as const;

interface Actor {
  id: string;
  label: string;
  sublabel: string;
  accent: string;
  icon: string;
}

// Fixed lanes, left to right. Order is deliberate: the request flows
// rightward into the trust/governance actors, then rightward again to the
// business system; returns point back left. The AI Assistant only routes
// and phrases — it is deliberately NOT styled as a trust node.
const ACTORS: Actor[] = [
  { id: 'you', label: 'You', sublabel: 'Signed-in person', accent: C.purple, icon: '\u{1F464}' },
  { id: 'ai', label: 'AI Assistant', sublabel: 'Routes only', accent: C.oktaBlue, icon: '\u{1F916}' },
  { id: 'okta', label: 'Okta', sublabel: 'Identity + pass', accent: C.oktaBlue, icon: '\u{1F510}' },
  { id: 'rules', label: 'Access Rules', sublabel: 'Relationship + context', accent: C.accent, icon: '\u{1F5C2}' },
  { id: 'approver', label: 'Approver', sublabel: 'Human sign-off', accent: C.purple, icon: '\u{1F44D}' },
  { id: 'system', label: 'Business System', sublabel: 'Inventory & more', accent: C.green, icon: '\u{1F4E6}' },
];

interface Message {
  from: string;
  to: string;
  label: string;
  caption: string;
  kind: MsgKind;
  note?: string;
}

interface Scenario {
  key: string;
  label: string;
  persona: Persona;
  question: string;
  messages: Message[];
  closingLine: string;
  branches?: { approve: Message[]; reject: Message[] };
}

// Content verified against the app's actual code (backend/auth/agent_config.py,
// fga_client.py, services/factory.py::APPROVAL_QUANTITY_THRESHOLD=500) rather
// than assumed — real scope strings and the real 500-unit approval threshold
// appear as note chips so the story stays grounded in what the system
// actually does, not a plausible-sounding paraphrase of it.
const SCENARIOS: Scenario[] = [
  {
    key: 'happy',
    label: 'Happy path',
    persona: 'sarah',
    question: 'How many climbing helmets do we have in stock?',
    messages: [
      { from: 'you', to: 'ai', kind: 'call', label: 'asks a question', caption: 'Sarah asks the assistant a question in plain English.' },
      { from: 'ai', to: 'okta', kind: 'call', label: "requests a pass, on Sarah's behalf", caption: "Before touching anything, the assistant asks Okta for permission, on Sarah's behalf." },
      { from: 'okta', to: 'ai', kind: 'return', label: 'issues a short-lived, scoped pass', caption: "Okta confirms it's really Sarah, and issues a pass good for ONE system, ONE purpose.", note: 'scope: inventory:read' },
      { from: 'ai', to: 'rules', kind: 'call', label: 'checks context', caption: "The assistant checks the live access rules for Sarah's relationship and context." },
      { from: 'rules', to: 'ai', kind: 'return', label: 'context is fine', caption: "Sarah's relationships and current context check out." },
      { from: 'ai', to: 'system', kind: 'call', label: 'uses the pass', caption: 'Now, and only now, the assistant reaches the inventory system with the narrow pass.' },
      { from: 'system', to: 'ai', kind: 'return', label: 'returns cleared data', caption: 'Inventory returns just the stock data Sarah is cleared to see.' },
      { from: 'ai', to: 'you', kind: 'return', label: 'answers', caption: 'Sarah gets a clear answer. The AI never had more power than she does.' },
    ],
    closingLine: 'Same pattern every time: verify the person, issue a narrow pass, check context, log it, then act.',
  },
  {
    key: 'denied',
    label: 'Access denied',
    persona: 'sarah',
    question: 'Set climbing-helmet stock to 50.',
    messages: [
      { from: 'you', to: 'ai', kind: 'call', label: 'asks to change inventory', caption: 'Sarah asks the assistant to change inventory: "Set climbing-helmet stock to 50."' },
      { from: 'ai', to: 'okta', kind: 'call', label: 'requests a write pass', caption: "The assistant asks Okta for permission to write, on Sarah's behalf." },
      { from: 'okta', to: 'ai', kind: 'deny', label: 'role not allowed — refused', caption: "Sarah's role can read inventory but not change it. Okta refuses — the whole request stops.", note: 'requested: inventory:write' },
    ],
    closingLine: 'The AI asked. Okta said no. The inventory system was never even contacted. Nothing leaked.',
  },
  {
    key: 'vacation',
    label: 'Blocked on vacation',
    persona: 'mike',
    question: "Add 200 units to my warehouse's stock.",
    messages: [
      { from: 'you', to: 'ai', kind: 'call', label: 'asks to adjust stock', caption: "Mike, a warehouse manager, asks to adjust his warehouse's stock." },
      { from: 'ai', to: 'okta', kind: 'call', label: 'requests a pass', caption: "The assistant asks Okta for permission, on Mike's behalf." },
      { from: 'okta', to: 'ai', kind: 'return', label: 'role + relationship OK', caption: "Mike's role and manager relationship both check out, so Okta issues the pass.", note: 'scope: inventory:write' },
      { from: 'ai', to: 'rules', kind: 'call', label: 'checks live context', caption: "The assistant checks the live access rules for Mike's warehouse." },
      { from: 'rules', to: 'ai', kind: 'deny', label: 'on vacation — blocked', caption: 'But the access rules see a live flag: Mike is on vacation right now. Blocked this second.', note: 'on_vacation: true' },
    ],
    closingLine: "Even a legitimate manager is blocked the instant context changes. Flip the flag back and he's in again. No code change needed.",
  },
  {
    key: 'approval',
    label: 'Needs approval',
    persona: 'mike',
    question: 'Add 10,000 units to warehouse stock.',
    messages: [
      { from: 'you', to: 'ai', kind: 'call', label: 'asks for a large change', caption: 'Mike asks to add a large amount of stock: 10,000 units.' },
      { from: 'ai', to: 'okta', kind: 'call', label: 'requests a write pass', caption: "The assistant asks Okta for permission, on Mike's behalf." },
      { from: 'okta', to: 'ai', kind: 'return', label: 'issues a scoped write pass', caption: 'Okta issues a scoped pass for warehouse writes.', note: 'scope: inventory:write' },
      { from: 'ai', to: 'rules', kind: 'call', label: 'checks context', caption: "The assistant confirms Mike isn't on vacation right now." },
      { from: 'rules', to: 'ai', kind: 'return', label: 'context is fine', caption: 'Context checks out too.' },
      { from: 'ai', to: 'approver', kind: 'approvalPause', label: 'high-impact — needs sign-off', caption: "This change is 10,000 units — big enough to require a human sign-off. The request pauses.", note: 'threshold: 500 units' },
    ],
    closingLine: '',
    branches: {
      approve: [
        { from: 'approver', to: 'ai', kind: 'return', label: 'approved', caption: 'Approved. Now, and only now, the large change is written.' },
        { from: 'ai', to: 'system', kind: 'call', label: 'writes the change', caption: 'The assistant writes the 10,000-unit adjustment.' },
        { from: 'system', to: 'ai', kind: 'return', label: 'confirms', caption: 'Inventory confirms the update.' },
        { from: 'ai', to: 'you', kind: 'return', label: 'confirms to Mike', caption: 'Mike gets confirmation that his 10,000-unit adjustment went through.' },
      ],
      reject: [
        { from: 'approver', to: 'ai', kind: 'deny', label: 'denied by approver', caption: 'A human denied it. The AI could not push it through on its own.' },
      ],
    },
  },
];

const VIEW_W = 980;
const MARGIN_X = 76;
const HEADER_H = 82;
const ROW_H = 44;
const ROW_TOP = HEADER_H + 18;
// A row whose message carries a note chip (e.g. "scope: inventory:read")
// packs a label, an arrow, AND a chip into one row -- more content than a
// plain row. Giving every row the same flat ROW_H left note rows cramped
// (label/chip crowding the next row's label). Only note rows get this
// extra height, so the fix doesn't undo the "fit on one screen" sizing
// for the ~80% of rows that don't have a note.
const NOTE_ROW_EXTRA_H = 20;

function rowHeight(m: Message): number {
  return ROW_H + (m.note ? NOTE_ROW_EXTRA_H : 0);
}

// Cumulative row centers, since rows are no longer a uniform height.
function computeRowCenters(messages: Message[]): number[] {
  const centers: number[] = [];
  let cursor = ROW_TOP;
  for (const m of messages) {
    const h = rowHeight(m);
    centers.push(cursor + h / 2);
    cursor += h;
  }
  return centers;
}

// How long the active arrow takes to draw itself, and how long it sits fully
// drawn before the next step begins. Slower than a typical UI transition on
// purpose — this is meant to be narrated/read step by step, not glanced at.
const DRAW_MS = 1100;
const PAUSE_MS = 900;

function laneX(actorIndex: number, count: number): number {
  const usable = VIEW_W - MARGIN_X * 2;
  return MARGIN_X + (usable * actorIndex) / (count - 1);
}

interface Props {
  title?: string;
}

export default function SequenceDiagram({ title = 'Sequence' }: Props) {
  const [scenarioKey, setScenarioKey] = useState('happy');
  const [branch, setBranch] = useState<'approve' | 'reject' | null>(null);
  const [played, setPlayed] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [awaitingDecision, setAwaitingDecision] = useState(false);

  const activeArrowRef = useRef<SVGLineElement | SVGPathElement | null>(null);
  const cancelledRef = useRef(false);
  const rafRef = useRef<number | null>(null);

  const scenario = useMemo(() => SCENARIOS.find((s) => s.key === scenarioKey)!, [scenarioKey]);

  const messages = useMemo<Message[]>(() => {
    if (scenario.branches && branch) return [...scenario.messages, ...scenario.branches[branch]];
    return scenario.messages;
  }, [scenario, branch]);

  const actorIndex = useCallback((id: string) => ACTORS.findIndex((a) => a.id === id), []);

  const activeStep = played > 0 ? messages[played - 1] : null;
  const activeActors = useMemo(() => {
    if (!activeStep) return new Set<string>();
    return new Set([activeStep.from, activeStep.to]);
  }, [activeStep]);

  const caption =
    played === 0
      ? `"${scenario.question}" — press Play to watch what happens.`
      : awaitingDecision
      ? messages[played - 1].caption
      : played >= messages.length
      ? branch === 'reject'
        ? 'A human stayed in the loop and said no.'
        : scenario.closingLine || messages[played - 1].caption
      : messages[played - 1].caption;

  const reset = useCallback(() => {
    cancelledRef.current = true;
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    setPlayed(0);
    setBranch(null);
    setIsPlaying(false);
    setAwaitingDecision(false);
  }, []);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  useEffect(() => {
    reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioKey]);

  const drawActiveArrow = useCallback((durationMs: number) => {
    return new Promise<void>((resolve) => {
      const el = activeArrowRef.current;
      if (!el) {
        resolve();
        return;
      }
      const len = el.getTotalLength();
      const sel = select(el);
      sel.attr('stroke-dasharray', `${len} ${len}`).attr('stroke-dashoffset', len).attr('opacity', 1);

      let start: number | null = null;
      const tick = (ts: number) => {
        if (cancelledRef.current) {
          resolve();
          return;
        }
        if (start === null) start = ts;
        const raw = Math.min((ts - start) / durationMs, 1);
        const u = easeCubicInOut(raw);
        sel.attr('stroke-dashoffset', len * (1 - u));
        if (raw < 1) {
          rafRef.current = requestAnimationFrame(tick);
        } else {
          resolve();
        }
      };
      rafRef.current = requestAnimationFrame(tick);
    });
  }, []);

  const play = useCallback(async () => {
    if (isPlaying) return;
    cancelledRef.current = false;
    setIsPlaying(true);
    setBranch(null);
    setPlayed(0);

    for (let i = 0; i < scenario.messages.length; i++) {
      if (cancelledRef.current) return;
      setPlayed(i + 1);
      await new Promise((r) => setTimeout(r, 20));
      await drawActiveArrow(DRAW_MS);

      const step = scenario.messages[i];
      if (step.kind === 'approvalPause') {
        setAwaitingDecision(true);
        setIsPlaying(false);
        return;
      }
      await new Promise((r) => setTimeout(r, PAUSE_MS));
    }
    setIsPlaying(false);
  }, [isPlaying, scenario, drawActiveArrow]);

  const decide = useCallback(
    async (choice: 'approve' | 'reject') => {
      if (!scenario.branches) return;
      setAwaitingDecision(false);
      setBranch(choice);
      setIsPlaying(true);
      cancelledRef.current = false;

      const branchMsgs = scenario.branches[choice];
      const base = scenario.messages.length;
      for (let i = 0; i < branchMsgs.length; i++) {
        if (cancelledRef.current) return;
        setPlayed(base + i + 1);
        await new Promise((r) => setTimeout(r, 20));
        await drawActiveArrow(DRAW_MS);
        await new Promise((r) => setTimeout(r, PAUSE_MS));
      }
      setIsPlaying(false);
    },
    [scenario, drawActiveArrow]
  );

  const scrubTo = useCallback(
    (n: number) => {
      if (isPlaying || awaitingDecision) return;
      setPlayed(n);
      cancelledRef.current = false;
      setTimeout(() => void drawActiveArrow(400), 20);
    },
    [isPlaying, awaitingDecision, drawActiveArrow]
  );

  const rowCenters = useMemo(() => computeRowCenters(messages), [messages]);
  const totalRowsHeight = useMemo(() => messages.reduce((sum, m) => sum + rowHeight(m), 0), [messages]);
  const svgHeight = ROW_TOP + totalRowsHeight + 32;
  const lifelineBottom = ROW_TOP + totalRowsHeight + 10;

  // "You"'s sublabel reflects whichever persona this scenario is about —
  // the sequence is inherently persona-specific (the approval/vacation
  // stories only make sense for a warehouse manager), so it's derived from
  // the scenario rather than an independent switcher.
  const youSublabel = scenario.persona === 'sarah' ? 'Signed in as Sarah' : 'Signed in as Mike';

  return (
    <div className="w-full rounded-2xl bg-[#0d0d14] border border-white/10 overflow-hidden shadow-2xl">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold text-slate-100">{title}</div>
          <div className="hidden sm:block text-xs text-slate-500">each column is an actor · read top to bottom</div>
        </div>
        <div className="flex items-center gap-2">
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              onClick={() => setScenarioKey(s.key)}
              disabled={isPlaying}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition disabled:opacity-50 ${
                scenarioKey === s.key
                  ? 'bg-orange-500/20 text-orange-300 border-orange-500/50'
                  : 'bg-white/5 text-slate-300 border-white/10 hover:border-white/25'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 px-5 py-2.5 border-b border-white/10 bg-black/20">
        <button
          onClick={() => (played === 0 || played >= messages.length ? play() : reset())}
          disabled={isPlaying}
          className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 disabled:opacity-50 transition"
        >
          {isPlaying ? 'Playing…' : played >= messages.length && played > 0 ? '↺ Replay' : '▶ Play'}
        </button>
        <button
          onClick={reset}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 border border-white/10 hover:border-white/25 transition"
        >
          Reset
        </button>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-400">
          <span className="tabular-nums">
            Step {Math.min(played, messages.length)} of {messages.length}
          </span>
          <div className="flex items-center gap-1">
            {messages.map((_, i) => {
              const isActive = i === played - 1;
              const isPlayed = i < played;
              return (
                <button
                  key={i}
                  onClick={() => scrubTo(i + 1)}
                  disabled={isPlaying || awaitingDecision || i >= played}
                  aria-label={`Go to step ${i + 1}`}
                  className={`h-2 rounded-full transition-all ${
                    isActive ? 'w-5 bg-orange-400' : isPlayed ? 'w-2 bg-orange-500/60' : 'w-2 bg-white/15'
                  } ${i < played && !isPlaying ? 'cursor-pointer' : 'cursor-default'}`}
                />
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <svg
          viewBox={`0 0 ${VIEW_W} ${svgHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="w-full h-auto block"
          role="img"
          aria-label="Sequence diagram: a request moving through each actor in order"
        >
          <defs>
            <marker id="seqArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 z" fill={C.laneActive} />
            </marker>
            <marker id="seqArrowDim" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 z" fill={C.lane} />
            </marker>
            <marker id="seqArrowDeny" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 z" fill={C.deny} />
            </marker>
          </defs>

          {ACTORS.map((a, i) => {
            const x = laneX(i, ACTORS.length);
            const isActive = activeActors.has(a.id);
            return (
              <line
                key={`life-${a.id}`}
                x1={x}
                y1={HEADER_H}
                x2={x}
                y2={lifelineBottom}
                stroke={isActive ? a.accent : C.lane}
                strokeOpacity={isActive ? 0.7 : 0.25}
                strokeWidth={isActive ? 2.5 : 1.5}
                style={{ transition: 'stroke 200ms, stroke-opacity 200ms, stroke-width 200ms' }}
              />
            );
          })}

          {ACTORS.map((a, i) => {
            const x = laneX(i, ACTORS.length);
            const isActive = activeActors.has(a.id);
            const w = 112;
            const h = 62;
            const sublabel = a.id === 'you' ? youSublabel : a.sublabel;
            return (
              <g key={`hdr-${a.id}`} transform={`translate(${x},${HEADER_H / 2})`}>
                <rect
                  x={-w / 2}
                  y={-h / 2}
                  width={w}
                  height={h}
                  rx={12}
                  fill={C.nodeFill}
                  stroke={a.accent}
                  strokeWidth={isActive ? 2.5 : 1.25}
                  style={{
                    filter: isActive ? `drop-shadow(0 0 12px ${a.accent}aa)` : 'none',
                    transition: 'stroke-width 200ms, filter 200ms',
                  }}
                />
                <text textAnchor="middle" y={-8} fontSize={18} className="select-none">
                  {a.icon}
                </text>
                <text textAnchor="middle" y={12} fontSize={12} fontWeight={600} fill={C.text} className="select-none">
                  {a.label}
                </text>
                <text textAnchor="middle" y={24} fontSize={9} fill={C.textDim} className="select-none">
                  {sublabel}
                </text>
              </g>
            );
          })}

          {messages.map((m, i) => {
            const y = rowCenters[i];
            const fromX = laneX(actorIndex(m.from), ACTORS.length);
            const toX = laneX(actorIndex(m.to), ACTORS.length);
            const isActive = i === played - 1;
            const isPlayed = i < played;
            const isFuture = i >= played;
            const rowOpacity = isActive ? 1 : isPlayed ? 0.5 : 0.14;
            const isDeny = m.kind === 'deny';
            const isPause = m.kind === 'approvalPause';

            if (m.kind === 'self') {
              const loopW = 46;
              return (
                <g key={`row-${i}`} opacity={rowOpacity} style={{ transition: 'opacity 250ms' }}>
                  <text x={fromX + loopW + 10} y={y - 6} fontSize={11} fill={isActive ? C.text : C.textDim} className="select-none">
                    {m.label}
                  </text>
                  <path
                    ref={isActive ? (activeArrowRef as React.Ref<SVGPathElement>) : undefined}
                    d={`M ${fromX} ${y - 10} h ${loopW} v 20 h ${-loopW}`}
                    fill="none"
                    stroke={isActive ? C.laneActive : C.lane}
                    strokeWidth={isActive ? 2.5 : 1.5}
                    strokeOpacity={isActive ? 1 : 0.6}
                    markerEnd={isActive ? 'url(#seqArrow)' : 'url(#seqArrowDim)'}
                  />
                  <circle cx={fromX} cy={y} r={11} fill={isActive ? C.laneActive : C.nodeFill} stroke={isActive ? C.laneActive : C.lane} strokeWidth={1.5} />
                  <text x={fromX} y={y + 4} textAnchor="middle" fontSize={11} fontWeight={700} fill={isActive ? '#fff' : C.textDim} className="select-none">
                    {i + 1}
                  </text>
                </g>
              );
            }

            const dir = toX >= fromX ? 1 : -1;
            const stroke = isDeny ? C.deny : isActive ? C.laneActive : C.lane;
            const midX = (fromX + toX) / 2;

            return (
              <g key={`row-${i}`} opacity={rowOpacity} style={{ transition: 'opacity 250ms' }}>
                <rect x={0} y={y - ROW_H / 2} width={VIEW_W} height={ROW_H} fill="transparent" className={isPlayed && !isPlaying ? 'cursor-pointer' : ''} onClick={() => isPlayed && !isPlaying && scrubTo(i + 1)} />
                <text x={midX} y={y - 9} textAnchor="middle" fontSize={11} fontWeight={isActive ? 600 : 400} fill={isDeny ? C.deny : isActive ? C.text : C.textDim} className="select-none">
                  {m.label}
                </text>
                <line
                  ref={isActive ? (activeArrowRef as React.Ref<SVGLineElement>) : undefined}
                  x1={fromX + dir * 12}
                  y1={y}
                  x2={toX - dir * 12}
                  y2={y}
                  stroke={stroke}
                  strokeWidth={isActive ? 3 : 2}
                  strokeOpacity={isFuture ? 0.6 : 1}
                  strokeDasharray={isDeny || m.kind === 'return' ? '7 5' : 'none'}
                  markerEnd={isDeny ? 'url(#seqArrowDeny)' : isActive ? 'url(#seqArrow)' : 'url(#seqArrowDim)'}
                />
                {m.note && (
                  <g transform={`translate(${midX}, ${y + 15})`}>
                    <rect x={-m.note.length * 3.2 - 6} y={-9} width={m.note.length * 6.4 + 12} height={18} rx={9} fill={isDeny ? '#3a0f0f' : '#0d1b2a'} stroke={isDeny ? C.deny : C.oktaBlue} strokeOpacity={0.6} strokeWidth={1} />
                    <text textAnchor="middle" y={4} fontSize={9.5} fontFamily="monospace" fill={isDeny ? C.deny : C.textDim} className="select-none">
                      {m.note}
                    </text>
                  </g>
                )}
                {isDeny && (
                  <g transform={`translate(${toX - dir * 12}, ${y})`}>
                    <circle r={9} fill="#1a0b0b" stroke={C.deny} strokeWidth={2} />
                    <line x1={-4} y1={4} x2={4} y2={-4} stroke={C.deny} strokeWidth={2} />
                    <line x1={-4} y1={-4} x2={4} y2={4} stroke={C.deny} strokeWidth={2} />
                  </g>
                )}
                {isPause && isActive && (
                  <g transform={`translate(${toX - dir * 12}, ${y})`}>
                    <circle r={9} fill={C.nodeFill} stroke={C.purple} strokeWidth={2} />
                    <line x1={-3} y1={-4} x2={-3} y2={4} stroke={C.purple} strokeWidth={2} />
                    <line x1={3} y1={-4} x2={3} y2={4} stroke={C.purple} strokeWidth={2} />
                  </g>
                )}
                <circle cx={fromX} cy={y} r={11} fill={isActive ? stroke : C.nodeFill} stroke={isActive ? stroke : C.lane} strokeWidth={1.5} />
                <text x={fromX} y={y + 4} textAnchor="middle" fontSize={11} fontWeight={700} fill={isActive ? '#fff' : C.textDim} className="select-none">
                  {i + 1}
                </text>
              </g>
            );
          })}
        </svg>

        <div className="px-5 py-3 border-t border-white/10 bg-black/20 min-h-[52px] flex items-center">
          <p className="text-sm text-slate-200 leading-snug">{caption}</p>
        </div>

        {awaitingDecision && (
          <div className="px-5 py-3 border-t border-white/10 bg-purple-950/40 flex items-center gap-3">
            <span className="text-xs text-slate-300">Awaiting a human decision:</span>
            <button onClick={() => decide('approve')} className="px-3 py-1.5 rounded-md text-xs font-semibold bg-green-600/80 hover:bg-green-600 text-white transition">
              Approve
            </button>
            <button onClick={() => decide('reject')} className="px-3 py-1.5 rounded-md text-xs font-semibold bg-red-600/80 hover:bg-red-600 text-white transition">
              Deny
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
