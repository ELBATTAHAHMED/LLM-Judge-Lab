import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import '@testing-library/jest-dom';
import { SelfPreferenceCard } from '../SelfPreferenceCard';
import type { SelfPreferenceResponse } from '../../api/types';

describe('SelfPreferenceCard Component (DOM Testing Library Audit)', () => {
  const emptyDataset: SelfPreferenceResponse = {
    judge_model: 'deepseek/deepseek-chat',
    judge_family: 'deepseek',
    self_win_rate: null,
    baseline_win_rate: 0.5234,
    self_preference_ratio: null,
    self_preference_detected: false,
    total_self_matchups: 0,
    total_other_matchups: 2271,
    p_value: null,
    statistically_significant: false,
  };

  const validDataset: SelfPreferenceResponse = {
    judge_model: 'gpt-4o-mini',
    judge_family: 'gpt',
    self_win_rate: 0.75,
    baseline_win_rate: 0.50,
    self_preference_ratio: 1.50,
    self_preference_detected: true,
    total_self_matchups: 100,
    total_other_matchups: 500,
    p_value: 0.0001,
    statistically_significant: true,
  };

  it('1. renders "Insufficient data" message and suppresses progress bars when total_self_matchups is 0', () => {
    render(<SelfPreferenceCard data={emptyDataset} loading={false} error={null} />);

    // Assert "Insufficient data" message IS in the DOM
    expect(
      screen.getByText(/Insufficient data: No rival-family pairings found for this judge model in the current dataset\./i)
    ).toBeInTheDocument();

    // Assert progress bar labels are NOT in the DOM
    expect(screen.queryByText(/Own Family Win Rate/i)).toBeNull();
    expect(screen.queryByText(/Rival Families \(Baseline\)/i)).toBeNull();
  });

  it('2. renders exact formatted percentages (75.0%) and detected status when given valid dataset', () => {
    render(<SelfPreferenceCard data={validDataset} loading={false} error={null} />);

    // Assert actual rendered percentage "75.0%" appears in DOM
    expect(screen.getByText('75.0%')).toBeInTheDocument();

    // Assert actual rendered baseline percentage "50.0%" appears in DOM
    expect(screen.getByText('50.0%')).toBeInTheDocument();

    // Assert detection status text is in DOM
    expect(screen.getByText(/Detected · 1.50×/i)).toBeInTheDocument();
  });

  it('3. asserts screen.queryByText(/50.0%/) is null when given emptyDataset', () => {
    render(<SelfPreferenceCard data={emptyDataset} loading={false} error={null} />);

    // Assert screen.queryByText(/50.0%/) is strictly null in rendered DOM
    expect(screen.queryByText(/50\.0%/)).toBeNull();
    expect(screen.queryByText(/p = 1\.0000/)).toBeNull();
  });
});
