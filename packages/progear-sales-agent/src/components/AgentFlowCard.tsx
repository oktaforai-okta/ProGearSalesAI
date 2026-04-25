'use client';

import { CheckCircle, XCircle, Clock, ArrowRight } from 'lucide-react';

interface AgentFlowStep {
  step: string;
  action: string;
  status: string;
  color?: string;
  agents?: string[];
}

interface Props {
  steps: AgentFlowStep[];
  isLoading?: boolean;
}

const agentColors: Record<string, string> = {
  sales: '#3b82f6',
  inventory: '#10b981',
  customer: '#8b5cf6',
  pricing: '#f59e0b',
};

const agentIcons: Record<string, string> = {
  sales: 'S',
  inventory: 'I',
  customer: 'C',
  pricing: 'P',
};

// Determine which technology handles each step
function getTechBadge(step: string): { label: string; color: string; bg: string } | null {
  if (step === 'router' || step.includes('routing')) {
    return { label: 'LangChain', color: '#854d0e', bg: '#fef3c7' }; // Yellow/amber for LangChain
  }
  if (step.includes('token') || step.includes('exchange')) {
    return { label: 'Okta', color: '#1e40af', bg: '#dbeafe' }; // Blue for Okta
  }
  if (step.includes('agent') && !step.includes('process')) {
    return { label: 'MCP', color: '#166534', bg: '#dcfce7' }; // Green for MCP servers
  }
  if (step === 'process_agents') {
    return { label: 'MCP', color: '#166534', bg: '#dcfce7' }; // Green for MCP
  }
  if (step === 'generate_response') {
    return { label: 'Claude', color: '#7c2d12', bg: '#ffedd5' }; // Orange for Claude
  }
  return null;
}

// Shorten action text to be more concise
function shortenAction(step: string, action: string): string {
  // Router steps
  if (action.includes('Analyzing request')) return 'Analyzing query...';
  if (action.includes('Selected agents')) {
    const match = action.match(/Selected agents?: (.+)/);
    return match ? `Selected: ${match[1]}` : action;
  }

  // Token exchange steps
  if (action.includes('Requesting access tokens')) return 'Requesting tokens...';
  if (action.includes('Token exchange complete')) {
    const match = action.match(/(\d+) granted, (\d+) denied/);
    if (match) return `✓ ${match[1]} granted${match[2] !== '0' ? `, ✗ ${match[2]} denied` : ''}`;
    return action;
  }

  // Process agents
  if (action.includes('Processing request through')) return 'Running authorized agents...';

  // Individual agents
  if (action.includes('Processed by')) {
    const match = action.match(/Processed by (.+)/);
    return match ? `Via ${match[1].replace('ProGear ', '').replace(' Agent', '')}` : action;
  }

  // Generate response
  if (action.includes('Generated combined')) return 'Response ready';

  return action;
}

export default function AgentFlowCard({ steps, isLoading }: Props) {
  // Extract agent steps for the visual flow
  const agentSteps = steps.filter(s =>
    s.step.includes('agent') || s.step === 'router' || s.step === 'generate_response'
  );

  // Get involved agents from routing step
  const routingStep = steps.find(s => s.step === 'router' && s.agents);
  const involvedAgents = routingStep?.agents || [];

  return (
    <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
      <div className="bg-gradient-to-r from-primary to-primary-light px-4 py-3 border-b border-neutral-border">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>Agent Flow</span>
          <span className="text-white/60 text-sm font-normal">— LangChain + Claude</span>
        </h3>
      </div>

      <div className="p-4">
        {/* Visual Agent Flow */}
        <div className="flex items-center justify-center gap-2 mb-4 pb-4 border-b border-gray-100">
          {/* Router */}
          <div className="flex flex-col items-center">
            <div className="w-10 h-10 rounded-lg bg-gray-700 text-white flex items-center justify-center text-xs font-bold">
              RT
            </div>
            <span className="text-[10px] text-gray-500 mt-1">Router</span>
          </div>

          <ArrowRight className="w-4 h-4 text-gray-400" />

          {/* Agents */}
          <div className="flex items-center gap-2">
            {['sales', 'inventory', 'customer', 'pricing'].map((agent) => {
              const isInvolved = involvedAgents.includes(agent);
              const agentStep = steps.find(s => s.step === `${agent}_agent`);
              const status = agentStep?.status || (isInvolved ? 'pending' : 'inactive');

              // Determine background color: red for denied, brand color otherwise
              const getBackgroundColor = () => {
                if (status === 'inactive') return undefined;
                if (status === 'denied') return '#ef4444'; // Red for denied
                return agentColors[agent]; // Brand color for all other states
              };

              return (
                <div key={agent} className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold transition-all ${
                      status === 'completed' ? 'text-white shadow-lg' :
                      status === 'denied' ? 'text-white shadow-lg' :
                      status === 'pending' ? 'text-white animate-pulse' :
                      'bg-gray-200 text-gray-400'
                    }`}
                    style={{
                      backgroundColor: getBackgroundColor()
                    }}
                  >
                    {status === 'completed' && <CheckCircle className="w-5 h-5" />}
                    {status === 'denied' && <XCircle className="w-5 h-5" />}
                    {status === 'pending' && <Clock className="w-5 h-5" />}
                    {status === 'inactive' && agentIcons[agent]}
                  </div>
                  <span className="text-[10px] text-gray-500 mt-1 capitalize">{agent}</span>
                </div>
              );
            })}
          </div>

          <ArrowRight className="w-4 h-4 text-gray-400" />

          {/* Response */}
          <div className="flex flex-col items-center">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold ${
              steps.some(s => s.step === 'generate_response' && s.status === 'completed')
                ? 'bg-success-green text-white'
                : 'bg-gray-200 text-gray-400'
            }`}>
              <CheckCircle className="w-5 h-5" />
            </div>
            <span className="text-[10px] text-gray-500 mt-1">Response</span>
          </div>
        </div>

        {/* Step Details */}
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {steps.map((step, idx) => {
            const techBadge = getTechBadge(step.step);
            const shortAction = shortenAction(step.step, step.action);

            return (
              <div
                key={idx}
                className={`flex items-start gap-3 p-2 rounded-lg text-sm ${
                  step.status === 'completed' ? 'bg-green-50' :
                  step.status === 'denied' ? 'bg-red-50' :
                  step.status === 'processing' ? 'bg-blue-50' :
                  'bg-gray-50'
                }`}
              >
                <div className={`mt-0.5 ${
                  step.status === 'completed' ? 'text-success-green' :
                  step.status === 'denied' ? 'text-error-red' :
                  step.status === 'processing' ? 'text-okta-blue' :
                  'text-gray-400'
                }`}>
                  {step.status === 'completed' && <CheckCircle className="w-4 h-4" />}
                  {step.status === 'denied' && <XCircle className="w-4 h-4" />}
                  {step.status === 'processing' && <Clock className="w-4 h-4 animate-spin" />}
                  {step.status === 'error' && <XCircle className="w-4 h-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-700 capitalize">
                      {step.step.replace(/_/g, ' ')}
                    </span>
                    {techBadge && (
                      <span
                        className="px-1.5 py-0.5 text-[10px] font-semibold rounded"
                        style={{
                          backgroundColor: techBadge.bg,
                          color: techBadge.color
                        }}
                      >
                        {techBadge.label}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    {shortAction}
                  </div>
                </div>
              </div>
            );
          })}

          {isLoading && (
            <div className="flex items-center gap-3 p-2 rounded-lg bg-blue-50">
              <Clock className="w-4 h-4 text-okta-blue animate-spin" />
              <span className="text-sm text-gray-600">Processing...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
