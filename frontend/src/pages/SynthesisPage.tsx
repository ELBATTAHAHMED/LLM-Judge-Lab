import React from 'react';
import { useControlledResults } from '../api/client';
import { ControlledEvidencePanel } from '../components/ControlledEvidencePanel';

export const SynthesisPage: React.FC = () => {
  const controlled = useControlledResults();
  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-4 font-sans">
      <div><h1 className="text-2xl font-serif">Final Scientific Synthesis</h1><p className="mt-1 text-xs text-neutral-500">Controlled RQ1–RQ7 evidence only; legacy exploratory dashboards are not used for final scientific conclusions.</p></div>
      <ControlledEvidencePanel {...controlled} />
    </div>
  );
};

export default SynthesisPage;
