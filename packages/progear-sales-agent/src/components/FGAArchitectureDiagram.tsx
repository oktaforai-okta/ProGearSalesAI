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
  detail: string;
  color: string;
};

type DiagramLink = {
  source: [number, number];
  target: [number, number];
  label: string;
  color: string;
};

const NODES: DiagramNode[] = [
  { id: 'okta', x: 24, y: 80, width: 160, height: 76, title: 'Okta profile', detail: 'Role level + vacation', color: '#2563eb' },
  { id: 'token', x: 244, y: 80, width: 160, height: 76, title: 'Access token', detail: 'Signed live claims', color: '#0284c7' },
  { id: 'fga', x: 464, y: 58, width: 184, height: 120, title: 'Auth0 FGA', detail: 'Role + quantity + context', color: '#7c3aed' },
  { id: 'allow', x: 712, y: 20, width: 164, height: 68, title: 'Execute', detail: 'Role meets the tier', color: '#059669' },
  { id: 'approve', x: 712, y: 126, width: 164, height: 68, title: 'Request approval', detail: 'Manager or VP', color: '#d97706' },
  { id: 'deny', x: 464, y: 236, width: 184, height: 58, title: 'Vacation = True', detail: 'Block every write', color: '#dc2626' },
];

const LINKS: DiagramLink[] = [
  { source: [184, 118], target: [244, 118], label: 'profile values', color: '#94a3b8' },
  { source: [404, 118], target: [464, 118], label: 'contextual tuples', color: '#94a3b8' },
  { source: [648, 96], target: [712, 54], label: 'allowed', color: '#059669' },
  { source: [648, 140], target: [712, 160], label: 'needs higher role', color: '#d97706' },
  { source: [556, 236], target: [556, 178], label: 'write blocker', color: '#dc2626' },
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
      .append('text')
      .attr('x', (link) => (link.source[0] + link.target[0]) / 2)
      .attr('y', (link) => (link.source[1] + link.target[1]) / 2 - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', (link) => link.color)
      .attr('font-size', 10)
      .attr('font-weight', 600)
      .text((link) => link.label);

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
      .attr('fill', '#172033')
      .attr('font-size', 14)
      .attr('font-weight', 700)
      .text((node) => node.title);

    nodes
      .append('text')
      .attr('x', 18)
      .attr('y', 52)
      .attr('fill', '#64748b')
      .attr('font-size', 11)
      .text((node) => node.detail);
  }, []);

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-2">
      <svg
        ref={svgRef}
        viewBox="0 0 900 310"
        className="min-w-[720px] w-full"
        role="img"
        aria-label="Okta sends the user's role and vacation status to Auth0 FGA. FGA either executes the inventory action, creates the required Manager or VP approval, or blocks a write while the user is on vacation."
      />
    </div>
  );
}
