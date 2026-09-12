import React from 'react';
import { useControlledResults } from '../api/client';
import { ControlledEvidencePanel } from '../components/ControlledEvidencePanel';

export const ControlledResultsPage: React.FC = () => {
  const state = useControlledResults();
  return <div className="mx-auto max-w-[1400px] space-y-5 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Final Controlled Experiments</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">Authoritative RQ1–RQ7 metrics from the frozen controlled analysis.</p></div></header>
    <ControlledEvidencePanel {...state} />
  </div>;
};
