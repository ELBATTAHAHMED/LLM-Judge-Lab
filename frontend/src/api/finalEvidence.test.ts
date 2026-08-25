import { describe, expect, it } from 'vitest';
import { formatMetricCi, formatMetricValue, metricLabel, rqInterpretation } from './finalEvidence';
import type { ControlledMetricResult } from './types';

const metric = (overrides: Partial<ControlledMetricResult>): ControlledMetricResult => ({
  rq: 'RQ1', metric: 'rq1_exact_agreement', metric_key: 'exact_agreement', judge: null, condition: null,
  value: 0.5919689119, numerator: 457, denominator: 772, eligible_n: 798, analyzed_n: 772,
  ties: 0, unknowns: 0, failures: 0, excluded: 0, ci_low: 0.5569948187, ci_high: 0.6269430052,
  status: 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'CONTROLLED', ...overrides,
});

describe('final controlled evidence presentation', () => {
  it('preserves RQ1 percentage, CI, and analyzed N scaling', () => {
    const rq1 = metric({});
    expect(formatMetricValue(rq1)).toBe('59.20%');
    expect(formatMetricCi(rq1)).toBe('95% CI: 55.70–62.69%');
    expect(rq1.denominator).toBe(772);
  });

  it('renders the counterbalanced RQ6 estimate and its cautious interpretation', () => {
    const rq6 = metric({ rq: 'RQ6', metric: 'rq6_counterbalanced_stable_same_family_preference', value: 0.5094339623, numerator: 81, denominator: 159, ci_low: 0.427672956, ci_high: 0.58490566 });
    expect(formatMetricValue(rq6)).toBe('50.94%');
    expect(formatMetricCi(rq6)).toBe('95% CI: 42.77–58.49%');
    expect(rqInterpretation('RQ6')).toMatch(/counterbalanced/i);
  });

  it('shows the RQ7 coverage trade-off and RQ5 controlled-data isolation wording', () => {
    const rq7 = metric({ rq: 'RQ7', metric: 'rq7_coverage_delta', metric_key: 'coverage_delta', value: -0.2102628285, ci_low: null, ci_high: null });
    expect(formatMetricValue(rq7)).toBe('-21.03 pp');
    expect(rqInterpretation('RQ7')).toMatch(/coverage loss/i);
    expect(rqInterpretation('RQ5')).toMatch(/presentation\/list-prefix/i);
    expect(metricLabel(metric({ rq: 'RQ5', metric: 'rq5_controlled_variant_win_rate' }))).toBe('Format variant win rate');
  });
});
