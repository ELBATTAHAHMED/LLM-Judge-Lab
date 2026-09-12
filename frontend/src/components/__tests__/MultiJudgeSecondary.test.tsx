import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it } from 'vitest';
import { ControlledEvidencePanel } from '../ControlledEvidencePanel';
import type { ControlledMetricResult, ControlledResultsResponse, MultiJudgeConsensusSecondary } from '../../api/types';

const metric = (metric_key: string, value: number): ControlledMetricResult => ({
  rq: 'RQ7', metric_key, judge: null, condition: null, metric: metric_key, value,
  numerator: null, denominator: 100, eligible_n: 100, analyzed_n: 100, ties: 0,
  unknowns: 0, failures: 0, excluded: 0, ci_low: null, ci_high: null,
  status: 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'CONTROLLED',
});

const multiJudge: MultiJudgeConsensusSecondary = {
  analysis_run_id: 'fc40faf1-b886-42f8-8faf-a616f61f3107', role: 'SECONDARY', method_family: 'cross_judge_aggregation',
  planned_n: 1611, retained_n: 1125, agreement: 0.7182222222, coverage: 0.6983240223,
  comparator: 'equal_weight_individual_judge_baseline_same_retained_pairs', comparator_agreement: 0.668,
  matched_delta: 0.0502222222, ci_95: { low: 0.0415555556, high: 0.0588888889 }, protocol_id: 'protocol', package_id: 'package',
  direct_dualswap_comparison: 'NOT_DEFENSIBLE', comparison_reason: 'different frozen units and estimands', coverage_unit: 'canonical_answer_pairs',
};

const response = (secondary_mitigations: ControlledResultsResponse['secondary_mitigations']): ControlledResultsResponse => ({
  status: 'CONTROLLED_RESULTS_AVAILABLE', evidence_class: 'CONTROLLED', executed_runs: 1, executed_passes: 1,
  accounting: null, analysis_runs: { RQ7: 'primary' }, secondary_mitigations,
  results: [metric('baseline_agreement', 0.6), metric('dual_swap_agreement', 0.7), metric('agreement_delta', 0.1), metric('baseline_coverage', 0.9), metric('dual_swap_coverage', 0.7), metric('coverage_delta', -0.2), metric('dual_swap_dual_pass_stability', 0.8)],
  message: 'frozen',
});

describe('RQ7 Multi-Judge secondary presentation', () => {
  it('renders the API-backed secondary without ranking it against primary DUAL_SWAP', () => {
    render(<ControlledEvidencePanel loading={false} error={null} data={response({ multi_judge_consensus: multiJudge })} />);
    fireEvent.click(screen.getByRole('button', { name: 'RQ7' }));
    expect(screen.getByText(/DUAL_SWAP is the main agreement–coverage analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/Multi-Judge is secondary\/exploratory mitigation evidence/i)).toBeInTheDocument();
    expect(screen.queryByText('Overall controlled result')).not.toBeInTheDocument();
    const dualSwap = screen.getByLabelText('DUAL_SWAP primary mitigation');
    const multiJudgePanel = screen.getByLabelText('Multi-Judge Consensus secondary mitigation');
    expect(dualSwap).toHaveClass('rounded-lg', 'border', 'bg-white');
    expect(multiJudgePanel).toHaveClass('rounded-lg', 'border', 'bg-white');
    expect(screen.getByTestId('controlled-dual-swap-header')).toHaveTextContent('Main analysis');
    expect(screen.getByTestId('controlled-multi-judge-header')).toHaveTextContent('Secondary / exploratory mitigation');
    expect([...screen.getByTestId('controlled-dual-swap-matrix').querySelectorAll('dt')].map((item) => item.textContent)).toEqual(['Agreement', 'Comparator', 'Matched delta', 'Coverage', '95% CI', 'Matched N']);
    expect([...screen.getByTestId('controlled-multi-judge-matrix').querySelectorAll('dt')].map((item) => item.textContent)).toEqual(['Agreement', 'Comparator', 'Matched delta', 'Coverage', '95% CI', 'Retained / planned']);
    expect(screen.getByTestId('controlled-dual-swap-footer')).toHaveTextContent(/Dual-pass stability/i);
    expect(screen.getByTestId('controlled-multi-judge-footer')).toHaveTextContent(/Positive only against the equal-weight individual-judge comparator/i);
    expect(screen.getByText(/equal-weight individual-judge comparator on the same retained consensus-covered pairs/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not a direct head-to-head effect/i)).toHaveLength(1);
    expect(screen.queryByText(/DUAL_SWAP − Multi-Judge/i)).not.toBeInTheDocument();
    expect(screen.queryByText('→')).not.toBeInTheDocument();
  });

  it('does not fabricate a secondary mitigation when the API omits it', () => {
    render(<ControlledEvidencePanel loading={false} error={null} data={response({})} />);
    fireEvent.click(screen.getByRole('button', { name: 'RQ7' }));
    expect(screen.getByLabelText('DUAL_SWAP primary mitigation')).toBeInTheDocument();
    expect(screen.queryByLabelText('Multi-Judge Consensus secondary mitigation')).not.toBeInTheDocument();
    expect(screen.queryByText(/^vs equal-weight individual-judge baseline/i)).not.toBeInTheDocument();
  });
});
