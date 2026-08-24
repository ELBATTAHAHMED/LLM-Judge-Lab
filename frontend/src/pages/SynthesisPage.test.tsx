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
  planned_n: 1611, retained_n: 1125, agreement: 0.7067, coverage: 0.6983,
  comparator: 'equal_weight_individual_judge_baseline_same_retained_pairs', comparator_agreement: 0.658,
  matched_delta: 0.0487, ci_95: { low: 0.0402, high: 0.0573 }, protocol_id: 'protocol', package_id: 'package',
  direct_dualswap_comparison: 'NOT_DEFENSIBLE', comparison_reason: 'different frozen units and estimands', coverage_unit: 'canonical_answer_pairs',
};

const response: ControlledResultsResponse = {
  status: 'CONTROLLED_RESULTS_AVAILABLE', evidence_class: 'CONTROLLED', executed_runs: 1, executed_passes: 1,
  accounting: null, analysis_runs: {}, secondary_mitigations: { multi_judge_consensus: multiJudge },
  results: [metric('RQ1', 'exact_agreement', 0.5), metric('RQ2', 'consistency', 0.9), metric('RQ3', 'paired_decisive_flip_rate', 0.1), metric('RQ4', 'variant_win_rate', 0.01), metric('RQ5', 'variant_win_rate', 0.02), metric('RQ6', 'stable_same_family_preference', 0.5), metric('RQ6', 'valid_stable_decisive_coverage', 0.3), metric('RQ7', 'baseline_agreement', 0.6), metric('RQ7', 'dual_swap_agreement', 0.7), metric('RQ7', 'agreement_delta', 0.1), metric('RQ7', 'dual_swap_coverage', 0.7), metric('RQ7', 'dual_swap_dual_pass_stability', 0.8)],
  message: 'frozen',
};

describe('SynthesisPage RQ7 secondary mitigation', () => {
  it('shows the API-backed secondary finding while preserving DUAL_SWAP as primary', () => {
    controlledState.value = { data: response, loading: false, error: null };
    render(<MemoryRouter><SynthesisPage /></MemoryRouter>);
    expect(screen.getByText('2 complementary strategies')).toBeInTheDocument();
    expect(screen.getByText('Reliability')).toBeInTheDocument();
    expect(screen.getByText('Controlled Effects')).toBeInTheDocument();
    const pairedGrid = screen.getByLabelText('Paired RQ1–RQ6 findings');
    expect(pairedGrid).toHaveClass('md:grid-cols-2');
    expect([...pairedGrid.children].map((child) => child.getAttribute('data-testid'))).toEqual(['finding-rq1', 'finding-rq4', 'finding-rq2', 'finding-rq5', 'finding-rq3', 'finding-rq6']);
    expect(screen.getByRole('heading', { name: 'Mitigation' })).toBeInTheDocument();
    expect(screen.getByLabelText('RQ7 Mitigation Strategies')).toHaveTextContent('Two complementary mitigation families.');
    expect(pairedGrid).not.toContainElement(screen.getByLabelText('RQ7 Mitigation Strategies'));
    expect(screen.getByLabelText('DUAL_SWAP primary synthesis finding')).toHaveClass('rounded-lg', 'border', 'bg-white');
    expect(screen.getByLabelText('Multi-Judge Consensus secondary synthesis finding')).toHaveClass('rounded-lg', 'border', 'bg-white');
    expect(screen.getByTestId('dual-swap-header')).toHaveTextContent('PRIMARY');
    expect(screen.getByTestId('multi-judge-header')).toHaveTextContent('SECONDARY');
    expect([...screen.getByTestId('dual-swap-matrix').querySelectorAll('dt')].map((item) => item.textContent)).toEqual(['Agreement', 'Matched delta', 'Coverage']);
    expect([...screen.getByTestId('multi-judge-matrix').querySelectorAll('dt')].map((item) => item.textContent)).toEqual(['Agreement', 'Matched delta', 'Coverage']);
    expect(screen.getByTestId('dual-swap-matrix')).toHaveTextContent('70.00%');
    expect(screen.getByTestId('multi-judge-matrix')).toHaveTextContent('70.67%');
    expect(screen.queryByText('Comparator')).not.toBeInTheDocument();
    expect(screen.queryByText('95% CI')).not.toBeInTheDocument();
    expect(screen.queryByText('Matched N')).not.toBeInTheDocument();
    expect(screen.queryByText('Retained / planned')).not.toBeInTheDocument();
    expect(screen.getByTestId('dual-swap-header')).toHaveTextContent('Presentation-consistency filtering');
    expect(screen.getByTestId('multi-judge-header')).toHaveTextContent('Cross-judge aggregation');
    expect(screen.getByTestId('dual-swap-footer')).toHaveTextContent(/Matched retained-decision comparison/i);
    expect(screen.getByTestId('multi-judge-footer')).toHaveTextContent(/equal-weight individual-judge baseline/i);
    expect(screen.getByText(/not a direct head-to-head comparison/i)).toBeInTheDocument();
  });
});
