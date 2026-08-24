import { describe, expect, it } from 'vitest';
import { isControlledMetricResult, isControlledResultsResponse } from './types';

const base = {
  rq: 'RQ7', judge: null, condition: null, metric: 'rq7_agreement_absolute_delta',
  value: -0.2, numerator: null, denominator: 8, eligible_n: 8, analyzed_n: 8,
  ties: 1, unknowns: 0, failures: 2, excluded: 2, ci_low: -0.4, ci_high: 0.0,
  status: 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'DRY_RUN_MOCK',
};

describe('controlled result contract', () => {
  it('accepts negative effects, CIs, failures, and nullable NOT_ESTIMABLE values', () => {
    expect(isControlledMetricResult(base)).toBe(true);
    expect(isControlledMetricResult({ ...base, value: null, numerator: null, denominator: null, ci_low: null, ci_high: null, status: 'NOT_ESTIMABLE' })).toBe(true);
  });

  it('rejects incomplete responses instead of coercing missing values to zero', () => {
    const { failures: _failures, ...incomplete } = base;
    expect(isControlledMetricResult(incomplete)).toBe(false);
  });

  it('requires controlled accounting and a complete metric payload before rendering final evidence', () => {
    const response = { status: 'CONTROLLED_RESULTS_AVAILABLE', evidence_class: 'CONTROLLED', executed_runs: 13_400, executed_passes: 16_600, accounting: { planned_units: 13_400, succeeded_units: 12_602, valid_partial_units: 523, failed_units: 275, pending_units: 0, planned_pass_slots: 16_600, valid_returned_passes: 16_228, failed_pass_slots: 372 }, analysis_runs: { RQ1: 'analysis-rq1' }, secondary_mitigations: {}, results: [{ ...base, evidence_class: 'CONTROLLED' }], message: 'frozen' };
    expect(isControlledResultsResponse(response)).toBe(true);
    expect(isControlledResultsResponse({ ...response, accounting: null })).toBe(true);
    expect(isControlledResultsResponse({ ...response, results: [{ ...base, denominator: undefined }] })).toBe(false);
  });
});
