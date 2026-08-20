export const EVIDENCE_CLASSES = ['LEGACY_EXPLORATORY', 'CONTROLLED', 'LIVE_SANDBOX', 'PLANNED', 'DRY_RUN_MOCK'] as const;
export type EvidenceClass = (typeof EVIDENCE_CLASSES)[number];

export const evidenceLabel: Record<EvidenceClass, string> = {
  LEGACY_EXPLORATORY: 'Exploratory',
  CONTROLLED: 'Controlled Evidence',
  LIVE_SANDBOX: 'Live Sandbox',
  PLANNED: 'Planned Experiment',
  DRY_RUN_MOCK: 'Mock / Dry Run',
};

export const isFinalControlledEvidence = (value: { evidence_class?: EvidenceClass } | null | undefined): boolean =>
  value?.evidence_class === 'CONTROLLED';
