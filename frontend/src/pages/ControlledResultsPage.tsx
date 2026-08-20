import React from 'react';
import { useControlledResults } from '../api/client';
import { ControlledEvidencePanel } from '../components/ControlledEvidencePanel';

export const ControlledResultsPage: React.FC = () => {
  const state = useControlledResults();
  return <div className="mx-auto max-w-[1400px] space-y-6 py-2"><div><h1 className="text-2xl font-serif">Final Controlled Experiments</h1><p className="mt-1 text-xs text-neutral-500">Authoritative RQ1–RQ7 results from the frozen controlled analysis. Metric values are rendered directly from /api/controlled/results.</p></div><ControlledEvidencePanel {...state} /></div>;
};
