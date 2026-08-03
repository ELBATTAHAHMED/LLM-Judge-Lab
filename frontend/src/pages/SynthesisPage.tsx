import React from 'react';
import { MacroSynthesisDashboard } from '../components/MacroSynthesisDashboard';

export const SynthesisPage: React.FC = () => {
  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-4 font-sans">
      <MacroSynthesisDashboard />
    </div>
  );
};

export default SynthesisPage;
