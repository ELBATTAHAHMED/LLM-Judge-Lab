import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it } from 'vitest';
import { isFinalControlledEvidence } from '../../api/evidence';
import { ControlledEvidencePanel } from '../ControlledEvidencePanel';
import { ControlledMetricCard } from '../ControlledMetricCard';
import type { ControlledMetricResult } from '../../api/types';

const controlledMetric = (rq: string, metric_key: string, value: number | null): ControlledMetricResult => ({
  rq, metric_key, judge: null, condition: null, metric: metric_key, value, numerator: null, denominator: 10,
  eligible_n: 10, analyzed_n: 10, ties: 0, unknowns: 0, failures: 0, excluded: 0, ci_low: null, ci_high: null,
  status: value === null ? 'UNBALANCED_PRESENTATION' : 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'CONTROLLED',
});

describe('controlled evidence separation', () => {
  it('does not treat legacy, sandbox, planned, or mock data as final controlled evidence', () => {
    for (const evidence_class of ['LEGACY_EXPLORATORY', 'LIVE_SANDBOX', 'PLANNED', 'DRY_RUN_MOCK'] as const) {
      expect(isFinalControlledEvidence({ evidence_class })).toBe(false);
    }
    expect(isFinalControlledEvidence({ evidence_class: 'CONTROLLED' })).toBe(true);
  });

  it('renders an explicit controlled empty state without legacy numbers', () => {
    render(<ControlledEvidencePanel loading={false} error={null} data={{ status: 'NO_CONTROLLED_EVIDENCE', evidence_class: 'CONTROLLED', executed_runs: 0, executed_passes: 0, accounting: null, analysis_runs: {}, secondary_mitigations: {}, results: [], message: 'planned' }} />);
    expect(screen.getByText('NO CONTROLLED EVIDENCE')).toBeInTheDocument();
    expect(screen.getByText(/Executed runs: 0; passes: 0/i)).toBeInTheDocument();
  });

  it('preserves negative deltas, CI, failures, and NOT_ESTIMABLE rather than coercing values to zero', () => {
    const metric = { rq: 'RQ7', judge: 'gpt-4o-mini', condition: 'DUAL_SWAP', metric: 'agreement_delta', value: -0.034, numerator: null, denominator: 800, eligible_n: 800, analyzed_n: 790, ties: 10, unknowns: 2, failures: 5, excluded: 3, ci_low: -0.05, ci_high: -0.01, status: 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'CONTROLLED' as const };
    const { rerender } = render(<ControlledMetricCard metric={metric} />);
    expect(screen.getByText('-3.40 pp')).toBeInTheDocument();
    expect(screen.getByText(/95% CI: -5.00–-1.00%/)).toBeInTheDocument();
    expect(screen.getByText(/Failures 5/)).toBeInTheDocument();
    rerender(<ControlledMetricCard metric={{ ...metric, value: null, denominator: null, ci_low: null, ci_high: null, status: 'NOT_ESTIMABLE' }} />);
    expect(screen.getAllByText('NOT ESTIMABLE')).toHaveLength(2);
    expect(screen.getByText(/CI not estimable/)).toBeInTheDocument();
  });

  it('uses local RQ navigation without replacing the overall controlled result', () => {
    render(<ControlledEvidencePanel loading={false} error={null} data={{
      status: 'CONTROLLED_RESULTS_AVAILABLE', evidence_class: 'CONTROLLED', executed_runs: 1, executed_passes: 1,
      accounting: { planned_units: 1, succeeded_units: 1, valid_partial_units: 0, failed_units: 0, pending_units: 0, planned_pass_slots: 1, valid_returned_passes: 1, failed_pass_slots: 0 },
      analysis_runs: { RQ1: 'pinned' }, secondary_mitigations: {},
      results: [controlledMetric('RQ1', 'exact_agreement', 0.5), controlledMetric('RQ6', 'stable_same_family_preference', 0.5094), controlledMetric('RQ6', 'judge:anthropic/claude-3-haiku:stable_same_family_preference', 0.8621), controlledMetric('RQ6', 'judge:gpt-4o-mini:stable_same_family_preference', 0.7576), controlledMetric('RQ6', 'judge:meta-llama/llama-3.3-70b-instruct:stable_same_family_preference', 0.09375), controlledMetric('RQ6', 'valid_stable_decisive_coverage', 0.33125), controlledMetric('RQ6', 'order_sensitive_disagreement', 0.2319), controlledMetric('RQ6', 'tie_or_abstention_rate', 0.5417), controlledMetric('RQ7', 'baseline_agreement', 0.6), controlledMetric('RQ7', 'dual_swap_agreement', 0.7), controlledMetric('RQ7', 'agreement_delta', 0.1), controlledMetric('RQ7', 'baseline_coverage', 0.9), controlledMetric('RQ7', 'dual_swap_coverage', 0.7), controlledMetric('RQ7', 'coverage_delta', -0.2), controlledMetric('RQ7', 'dual_swap_dual_pass_stability', 0.8)],
      message: 'frozen',
    }} />);
    expect(screen.getByRole('heading', { name: /RQ1.*Human Alignment/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'RQ6' }));
    expect(screen.getByText('Stable same-family preference')).toBeInTheDocument();
    expect(screen.getByText(/no eligible source data/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'RQ7' }));
    expect(screen.getByText('Dual-pass stability')).toBeInTheDocument();
  });
});
