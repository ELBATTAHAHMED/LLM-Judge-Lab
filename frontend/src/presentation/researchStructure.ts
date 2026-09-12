/**
 * Presentation-only research structure.
 *
 * This module intentionally sits outside the API contract and scientific
 * evidence model. It groups existing internal RQ identifiers for display; it
 * does not rename, recalculate, or otherwise reinterpret an AnalysisRun.
 */
export type InternalRqId = 'RQ1' | 'RQ2' | 'RQ3' | 'RQ4' | 'RQ5' | 'RQ6' | 'RQ7';
export type MainQuestionId = 'MAIN_Q1' | 'MAIN_Q2' | 'MAIN_Q3';
export type PresentationRole = 'MAIN' | 'SECONDARY' | 'EXPLORATORY';
export type MitigationRole = 'PRIMARY' | 'SECONDARY' | null;

export interface ResearchQuestionPresentation {
  internalRqId: InternalRqId;
  displayTitle: string;
  shortPresentationLabel: string;
  role: PresentationRole;
  parentMainQuestion: MainQuestionId | null;
  displayOrder: number;
  mitigationRole: MitigationRole;
  interpretation: string;
}

export interface MainQuestionPresentation {
  id: MainQuestionId;
  displayLabel: string;
  displayTitle: string;
  internalRqIds: InternalRqId[];
  displayOrder: number;
}

export interface MitigationPresentation {
  id: 'DUAL_SWAP' | 'MULTI_JUDGE_CONSENSUS';
  displayTitle: string;
  shortPresentationLabel: string;
  role: 'PRIMARY' | 'SECONDARY';
  internalRqId: 'RQ7';
  parentMainQuestion: 'MAIN_Q3';
  displayOrder: number;
  family: string;
  exploratory: boolean;
}

export const MAIN_QUESTION_PRESENTATION: readonly MainQuestionPresentation[] = [
  { id: 'MAIN_Q1', displayLabel: 'Main Question 1', displayTitle: 'Human Agreement', internalRqIds: ['RQ1'], displayOrder: 1 },
  { id: 'MAIN_Q2', displayLabel: 'Main Question 2', displayTitle: 'Stability', internalRqIds: ['RQ2', 'RQ3'], displayOrder: 2 },
  { id: 'MAIN_Q3', displayLabel: 'Main Question 3', displayTitle: 'Mitigation', internalRqIds: ['RQ7'], displayOrder: 3 },
];

export const RESEARCH_QUESTION_PRESENTATION: readonly ResearchQuestionPresentation[] = [
  {
    internalRqId: 'RQ1', displayTitle: 'Human Alignment', shortPresentationLabel: 'Human Alignment', role: 'MAIN', parentMainQuestion: 'MAIN_Q1', displayOrder: 1, mitigationRole: null,
    interpretation: 'Agreement is measured against human preference reference labels; it is not an accuracy claim.',
  },
  {
    internalRqId: 'RQ2', displayTitle: 'Stochastic Consistency', shortPresentationLabel: 'Stochastic Consistency', role: 'MAIN', parentMainQuestion: 'MAIN_Q2', displayOrder: 2, mitigationRole: null,
    interpretation: 'Primary: fixed-temperature strict complete-repetition consistency. Conditional returned-judgment consistency is a sensitivity analysis, not a temperature-effect estimate.',
  },
  {
    internalRqId: 'RQ3', displayTitle: 'Position Sensitivity', shortPresentationLabel: 'Position Sensitivity', role: 'MAIN', parentMainQuestion: 'MAIN_Q2', displayOrder: 3, mitigationRole: null,
    interpretation: 'Position sensitivity is measured after canonical answer-identity remapping under answer-order swaps.',
  },
  {
    internalRqId: 'RQ4', displayTitle: 'Controlled Redundant-Length Effect', shortPresentationLabel: 'Redundant-Length', role: 'SECONDARY', parentMainQuestion: null, displayOrder: 4, mitigationRole: null,
    interpretation: 'Narrow frozen estimator: stable controlled redundant-text variant wins among valid controlled pairs; this is not a broad verbosity-bias claim.',
  },
  {
    internalRqId: 'RQ5', displayTitle: 'Controlled Presentation-Format Effect', shortPresentationLabel: 'Presentation Format', role: 'SECONDARY', parentMainQuestion: null, displayOrder: 5, mitigationRole: null,
    interpretation: 'Narrow frozen estimator: stable controlled presentation/list-prefix variant wins among valid controlled pairs; this is not a general formatting-effect claim.',
  },
  {
    internalRqId: 'RQ6', displayTitle: 'Counterbalanced Matched Source-Family Preference', shortPresentationLabel: 'Source-Family Preference', role: 'EXPLORATORY', parentMainQuestion: null, displayOrder: 6, mitigationRole: null,
    interpretation: 'Counterbalanced matched source-family association only. Strong judge-level heterogeneity remains; source/content-quality confounding prevents a causal self-bias claim.',
  },
  {
    internalRqId: 'RQ7', displayTitle: 'Mitigation Trade-off', shortPresentationLabel: 'Mitigation', role: 'MAIN', parentMainQuestion: 'MAIN_Q3', displayOrder: 7, mitigationRole: 'PRIMARY',
    interpretation: 'DUAL_SWAP has a small matched point difference with a confidence interval crossing zero and substantial coverage loss. Multi-Judge is positive only against its own equal-weight comparator on retained consensus-covered pairs; they are not directly comparable.',
  },
];

export const MITIGATION_PRESENTATION: readonly MitigationPresentation[] = [
  {
    id: 'DUAL_SWAP', displayTitle: 'DUAL_SWAP', shortPresentationLabel: 'DUAL_SWAP', role: 'PRIMARY', internalRqId: 'RQ7', parentMainQuestion: 'MAIN_Q3', displayOrder: 1,
    family: 'Presentation-consistency filtering', exploratory: false,
  },
  {
    id: 'MULTI_JUDGE_CONSENSUS', displayTitle: 'Multi-Judge Consensus', shortPresentationLabel: 'Multi-Judge', role: 'SECONDARY', internalRqId: 'RQ7', parentMainQuestion: 'MAIN_Q3', displayOrder: 2,
    family: 'Cross-judge aggregation', exploratory: true,
  },
];

export const RESEARCH_QUESTION_BY_ID: Readonly<Record<InternalRqId, ResearchQuestionPresentation>> = Object.fromEntries(
  RESEARCH_QUESTION_PRESENTATION.map((entry) => [entry.internalRqId, entry]),
) as Record<InternalRqId, ResearchQuestionPresentation>;

export const MITIGATION_BY_ID: Readonly<Record<MitigationPresentation['id'], MitigationPresentation>> = Object.fromEntries(
  MITIGATION_PRESENTATION.map((entry) => [entry.id, entry]),
) as Record<MitigationPresentation['id'], MitigationPresentation>;

export const DETAILED_RQ_ORDER: readonly InternalRqId[] = RESEARCH_QUESTION_PRESENTATION
  .toSorted((left, right) => left.displayOrder - right.displayOrder)
  .map((entry) => entry.internalRqId);

export const presentationForRq = (rq: string): ResearchQuestionPresentation | undefined => RESEARCH_QUESTION_BY_ID[rq as InternalRqId];
