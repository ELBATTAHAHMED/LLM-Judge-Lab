import React from 'react';
import { MacroSynthesisDashboard } from '../components/MacroSynthesisDashboard';
import { EvidenceBadge } from '../components/EvidenceBadge';

export const SynthesisPage: React.FC = () => {
  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-4 font-sans">
      <div><EvidenceBadge evidenceClass="LEGACY_EXPLORATORY" /><p className="mt-2 text-xs text-neutral-500">Historical exploratory comparison only. Controlled mitigation evaluation is planned and has not yet run.</p></div>
      <MacroSynthesisDashboard />
    </div>
  );
};

export default SynthesisPage;
