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
  color: string;
};

const NODES: DiagramNode[] = [
  { id: 'okta', x: 28, y: 126, width: 170, height: 78, title: 'Okta identity', detail: 'Role + vacation', color: '#2563eb' },
  { id: 'token', x: 255, y: 126, width: 170, height: 78, title: 'Inventory token', detail: 'Signed live claims', color: '#0284c7' },
  { id: 'fga', x: 492, y: 105, width: 195, height: 120, title: 'FGA', detail: 'Role + action + quantity', color: '#7c3aed' },
  { id: 'allow', x: 772, y: 30, width: 178, height: 70, title: 'Execute', detail: 'Role is high enough', color: '#059669' },
  { id: 'approve', x: 772, y: 137, width: 178, height: 70, title: 'Ask for approval', detail: 'Manager or VP', color: '#d97706' },
  { id: 'deny', x: 772, y: 244, width: 178, height: 70, title: 'Block the write', detail: 'Vacation is True', color: '#dc2626' },
];

const LINKS: DiagramLink[] = [
  { source: [198, 165], target: [255, 165], color: '#94a3b8' },
  { source: [425, 165], target: [492, 165], color: '#94a3b8' },
  { source: [687, 133], target: [772, 65], color: '#059669' },
  { source: [687, 165], target: [772, 172], color: '#d97706' },
  { source: [687, 197], target: [772, 279], color: '#dc2626' },
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
      .text((node) => node.detail);
  }, []);

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-950/60">
      <svg
        ref={svgRef}
        viewBox="0 0 980 344"
        className="w-full min-w-[760px]"
        role="img"
        aria-label="Okta sends the user's role and vacation status to FGA. FGA either executes the inventory action, creates the required Manager or VP approval, or blocks a write while the user is on vacation."
      />
    </div>
  );
}
