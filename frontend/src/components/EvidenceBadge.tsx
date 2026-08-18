import React from 'react';
import { evidenceLabel, type EvidenceClass } from '../api/evidence';

export const EvidenceBadge: React.FC<{ evidenceClass: EvidenceClass }> = ({ evidenceClass }) => {
  const tone = evidenceClass === 'CONTROLLED' ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300' : evidenceClass === 'DRY_RUN_MOCK' ? 'border-amber-500/50 text-amber-700 dark:text-amber-300' : 'border-neutral-300 text-neutral-600 dark:border-neutral-700 dark:text-neutral-300';
  return <span className={`inline-flex rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${tone}`}>{evidenceLabel[evidenceClass]}</span>;
};
