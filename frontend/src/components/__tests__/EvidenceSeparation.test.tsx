import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it } from 'vitest';
import { isFinalControlledEvidence } from '../../api/evidence';
import { ControlledEvidencePanel } from '../ControlledEvidencePanel';
import { ControlledMetricCard } from '../ControlledMetricCard';

describe('controlled evidence separation', () => {
  it('does not treat legacy, sandbox, planned, or mock data as final controlled evidence', () => {
    for (const evidence_class of ['LEGACY_EXPLORATORY', 'LIVE_SANDBOX', 'PLANNED', 'DRY_RUN_MOCK'] as const) {
      expect(isFinalControlledEvidence({ evidence_class })).toBe(false);
    }
    expect(isFinalControlledEvidence({ evidence_class: 'CONTROLLED' })).toBe(true);
  });

  it('renders an explicit controlled empty state without legacy numbers', () => {
    render(<ControlledEvidencePanel loading={false} error={null} data={{ status: 'NO_CONTROLLED_EVIDENCE', evidence_class: 'CONTROLLED', executed_runs: 0, executed_passes: 0, results: [], message: 'planned' }} />);
    expect(screen.getByText('NO CONTROLLED EVIDENCE YET')).toBeInTheDocument();
    expect(screen.getByText(/Executed runs: 0; passes: 0/i)).toBeInTheDocument();
  });

  it('preserves negative deltas, CI, failures, and NOT_ESTIMABLE rather than coercing values to zero', () => {
    const metric = { rq: 'RQ7', judge: 'gpt-4o-mini', condition: 'DUAL_SWAP', metric: 'agreement_delta', value: -0.034, numerator: null, denominator: 800, eligible_n: 800, analyzed_n: 790, ties: 10, unknowns: 2, failures: 5, excluded: 3, ci_low: -0.05, ci_high: -0.01, status: 'ESTIMABLE', analysis_version: 'phase4-analysis-v1', evidence_class: 'CONTROLLED' as const };
    const { rerender } = render(<ControlledMetricCard metric={metric} />);
    expect(screen.getByText('-3.4%')).toBeInTheDocument();
    expect(screen.getByText(/95% CI: -5.0%–-1.0%/)).toBeInTheDocument();
    expect(screen.getByText(/Failures 5/)).toBeInTheDocument();
    rerender(<ControlledMetricCard metric={{ ...metric, value: null, denominator: null, ci_low: null, ci_high: null, status: 'NOT_ESTIMABLE' }} />);
    expect(screen.getAllByText('Not estimable')).toHaveLength(2);
    expect(screen.getByText(/CI not estimable/)).toBeInTheDocument();
  });
});
