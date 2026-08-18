import React from 'react';
import { useControlledResults } from '../api/client';
import { ControlledEvidencePanel } from '../components/ControlledEvidencePanel';

const rqLabels = ['RQ1 · Agreement with Human Preferences', 'RQ2 · Stochastic Consistency', 'RQ3 · Position Sensitivity', 'RQ4 · Controlled Redundant-Length Effect', 'RQ5 · Controlled Format Effect', 'RQ6 · Matched Source-Family Preference', 'RQ7 · Mitigation Evaluation'];

export const ControlledResultsPage: React.FC = () => {
  const state = useControlledResults();
  return <div className="mx-auto max-w-[1400px] space-y-6 py-2"><div><h1 className="text-2xl font-serif">Controlled Experiments</h1><p className="mt-1 text-xs text-neutral-500">Authoritative final evidence is displayed only after frozen-protocol execution and Phase 4 analysis.</p></div><ControlledEvidencePanel {...state} /><section><h2 className="mb-3 text-xs font-mono uppercase tracking-wider text-neutral-500">Planned protocol coverage</h2><div className="grid gap-3 md:grid-cols-2">{rqLabels.map((label) => <div className="rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800" key={label}><strong>{label}</strong><p className="mt-1 text-xs text-neutral-500">Status: Awaiting Controlled Execution. Future display supports N, CI, ties, unknowns, failures, exclusions, and signed effects.</p></div>)}</div></section></div>;
};
