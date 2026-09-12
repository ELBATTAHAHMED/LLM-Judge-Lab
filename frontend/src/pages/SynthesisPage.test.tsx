import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ControlledMetricResult, ControlledResultsResponse, MultiJudgeConsensusSecondary } from '../api/types';

const controlledState = vi.hoisted(() => ({ value: null as unknown }));
vi.mock('../api/client', () => ({ useControlledResults: () => controlledState.value }));

import { SynthesisPage } from './SynthesisPage';

const metric = (rq: string, metric_key: string, value: number): ControlledMetricResult => ({
  rq, metric_key, judge: null, condition: null, metric: metric_key, value, numerator: null, denominator: 100,
  eligible_n: 100, analyzed_n: 100, ties: 0, unknowns: 0, failures: 0, excluded: 0, ci_low: null, ci_high: null,
  status: 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'CONTROLLED',
});

const multiJudge: MultiJudgeConsensusSecondary = {
  analysis_run_id: 'fc40faf1-b886-42f8-8faf-a616f61f3107', role: 'SECONDARY', method_family: 'cross_judge_aggregation',
  planned_n: 1611, retained_n: 1125, agreement: 0.7182222222, coverage: 0.6983240223,
  comparator: 'equal_weight_individual_judge_baseline_same_retained_pairs', comparator_agreement: 0.668,
  matched_delta: 0.0502222222, ci_95: { low: 0.0415555556, high: 0.0588888889 }, protocol_id: 'protocol', package_id: 'package',
  direct_dualswap_comparison: 'NOT_DEFENSIBLE', comparison_reason: 'different frozen units and estimands', coverage_unit: 'canonical_answer_pairs',
};

const response: ControlledResultsResponse = {
  status: 'CONTROLLED_RESULTS_AVAILABLE', evidence_class: 'CONTROLLED', executed_runs: 1, executed_passes: 1,
  accounting: null, analysis_runs: {}, secondary_mitigations: { multi_judge_consensus: multiJudge },
  results: [metric('RQ1', 'exact_agreement', 0.5), metric('RQ2', 'consistency', 0.9), metric('RQ3', 'paired_decisive_flip_rate', 0.1), metric('RQ4', 'variant_win_rate', 0.01), metric('RQ5', 'variant_win_rate', 0.02), metric('RQ6', 'stable_same_family_preference', 0.5), metric('RQ6', 'valid_stable_decisive_coverage', 0.3), metric('RQ7', 'baseline_agreement', 0.6), metric('RQ7', 'dual_swap_agreement', 0.7), metric('RQ7', 'agreement_delta', 0.1), metric('RQ7', 'baseline_coverage', 0.9), metric('RQ7', 'dual_swap_coverage', 0.7), metric('RQ7', 'coverage_delta', -0.2), metric('RQ7', 'dual_swap_dual_pass_stability', 0.8)],
  message: 'frozen',
};

describe('SynthesisPage research hierarchy', () => {
  it('shows three principal questions before supporting and additional mitigation analyses', () => {
    controlledState.value = { data: response, loading: false, error: null };
    render(<MemoryRouter><SynthesisPage /></MemoryRouter>);
    const principal = screen.getByLabelText('Principal research questions');
    expect(principal).toHaveTextContent('Main Question 1');
    expect(principal).toHaveTextContent('Main Question 2');
    expect(principal).toHaveTextContent('Main Question 3');
    expect(screen.getByLabelText('Main Question 2 Stability')).toHaveTextContent('RQ2');
    expect(screen.getByLabelText('Main Question 2 Stability')).toHaveTextContent('RQ3');
    expect(screen.getByLabelText('Main Question 3 Mitigation')).toHaveTextContent('DUAL_SWAP');
    expect(screen.getByLabelText('Secondary analyses')).toHaveTextContent('RQ4');
    expect(screen.getByLabelText('Secondary analyses')).toHaveTextContent('RQ5');
    expect(screen.getByLabelText('Exploratory analysis')).toHaveTextContent('RQ6');
    expect(screen.getByLabelText('Additional Multi-Judge mitigation analysis')).toHaveTextContent('Secondary / exploratory mitigation');
    expect(screen.queryByText('Comparator')).not.toBeInTheDocument();
    expect(screen.getByText(/not a direct head-to-head comparison/i)).toBeInTheDocument();
  });
});
