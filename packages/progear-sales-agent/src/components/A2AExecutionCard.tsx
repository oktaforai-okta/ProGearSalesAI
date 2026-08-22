'use client';

import { ChainOfCustody, type A2ATraceEvent } from './ChainOfCustody';

export type { A2ATraceEvent } from './ChainOfCustody';

export function A2AExecutionCard({
  events,
  subject,
}: {
  events?: A2ATraceEvent[];
  subject?: string | null;
}) {
  return <ChainOfCustody events={events} subject={subject} compact showInspectLink />;
}
