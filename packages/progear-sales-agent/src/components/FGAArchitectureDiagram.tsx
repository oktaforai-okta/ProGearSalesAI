'use client';

import { useEffect, useRef } from 'react';
import { select } from 'd3-selection';
import { linkHorizontal } from 'd3-shape';

type DiagramNode = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  title: string;
  detail: string[];
  color: string;
};

type DiagramLink = {
  source: [number, number];
  target: [number, number];
  color: string;
  label?: string;
  labelAt?: [number, number];
};

const NODES: DiagramNode[] = [
  { id: 'okta', x: 20, y: 132, width: 165, height: 86, title: 'Okta profile', detail: ['Clearance 0, 1, or 2', 'Manager + vacation'], color: '#2563eb' },
  { id: 'delegation', x: 230, y: 112, width: 185, height: 126, title: 'Delegation gate', detail: ['Vacation = False', 'Agent may continue'], color: '#0f766e' },
  { id: 'token', x: 470, y: 132, width: 165, height: 86, title: 'Inventory token', detail: ['Signed live role', 'Scoped resource access'], color: '#0284c7' },
  { id: 'fga', x: 690, y: 112, width: 185, height: 126, title: 'FGA', detail: ['Role + action', '+ quantity'], color: '#7c3aed' },
  { id: 'allow', x: 950, y: 24, width: 180, height: 76, title: 'Execute', detail: ['Role meets the tier'], color: '#059669' },
  { id: 'approve', x: 950, y: 144, width: 180, height: 76, title: 'Ask for approval', detail: ['Manager 601+ → VP'], color: '#d97706' },
  { id: 'deny', x: 950, y: 264, width: 180, height: 76, title: 'Block the write', detail: ['Sales is read-only'], color: '#dc2626' },
  { id: 'away', x: 230, y: 300, width: 185, height: 76, title: 'Stop delegation', detail: ['Vacation = True', 'No ID-JAG requested'], color: '#dc2626' },
];

const LINKS: DiagramLink[] = [
  { source: [185, 175], target: [230, 175], color: '#94a3b8' },
  { source: [415, 175], target: [470, 175], color: '#0f766e', label: 'False', labelAt: [443, 162] },
  { source: [322, 238], target: [322, 300], color: '#dc2626', label: 'True', labelAt: [340, 273] },
  { source: [635, 175], target: [690, 175], color: '#94a3b8' },
  { source: [875, 143], target: [950, 62], color: '#059669' },
  { source: [875, 175], target: [950, 182], color: '#d97706' },
  { source: [875, 207], target: [950, 302], color: '#dc2626' },
];

export default function FGAArchitectureDiagram() {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = select(svgRef.current);
    svg.selectAll('g[data-layer="diagram"]').remove();
    const layer = svg.append('g').attr('data-layer', 'diagram');
    const horizontalLink = linkHorizontal<DiagramLink, [number, number]>()
      .x((point) => point[0])
      .y((point) => point[1]);

    const links = layer
      .append('g')
      .selectAll('g')
      .data(LINKS)
      .join('g');

    links
      .append('path')
      .attr('d', (link) => horizontalLink(link))
      .attr('fill', 'none')
      .attr('stroke', (link) => link.color)
      .attr('stroke-width', 2.5)
      .attr('stroke-linecap', 'round');

    links
      .filter((link) => Boolean(link.label && link.labelAt))
      .append('text')
      .attr('x', (link) => link.labelAt?.[0] ?? 0)
      .attr('y', (link) => link.labelAt?.[1] ?? 0)
      .attr('text-anchor', 'middle')
      .attr('class', 'fill-slate-600 dark:fill-slate-300')
      .attr('font-size', 10)
      .attr('font-weight', 700)
      .text((link) => link.label ?? '');

    const nodes = layer
      .append('g')
      .selectAll('g')
      .data(NODES)
      .join('g')
      .attr('transform', (node) => `translate(${node.x},${node.y})`);

    nodes
      .append('rect')
      .attr('width', (node) => node.width)
      .attr('height', (node) => node.height)
      .attr('rx', 14)
      .attr('fill', (node) => `${node.color}12`)
      .attr('stroke', (node) => node.color)
      .attr('stroke-width', 2);

    nodes
      .append('circle')
      .attr('cx', 22)
      .attr('cy', 24)
      .attr('r', 7)
      .attr('fill', (node) => node.color);

    nodes
      .append('text')
      .attr('x', 38)
      .attr('y', 29)
      .attr('class', 'fill-slate-900 dark:fill-slate-100')
      .attr('font-size', 14)
      .attr('font-weight', 700)
      .text((node) => node.title);

    nodes
      .append('text')
      .attr('x', 18)
      .attr('y', 52)
      .attr('class', 'fill-slate-500 dark:fill-slate-300')
      .attr('font-size', 11)
      .selectAll('tspan')
      .data((node) => node.detail)
      .join('tspan')
      .attr('x', 18)
      .attr('dy', (_, index) => index === 0 ? 0 : 17)
      .text((line) => line);
  }, []);

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-950/60">
      <svg
        ref={svgRef}
        viewBox="0 0 1150 400"
        className="w-full min-w-[760px]"
        role="img"
        aria-label="Okta profile context reaches a delegation gate. Vacation true stops before ID-JAG. Vacation false allows a scoped Inventory token, then FGA uses role, action, and quantity to execute, request VP approval, or block the write."
      />
    </div>
  );
}
