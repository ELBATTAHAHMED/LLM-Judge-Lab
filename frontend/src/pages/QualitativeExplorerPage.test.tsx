import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { JudgeProvider } from '../context/JudgeContext';
import { ThemeProvider } from '../context/ThemeContext';
import type { QualitativeRecord } from '../api/types';
import { QualitativeExplorerPage } from './QualitativeExplorerPage';

const { useQualitativeBucket } = vi.hoisted(() => ({ useQualitativeBucket: vi.fn() }));

vi.mock('../api/client', () => ({ useQualitativeBucket }));

const records: QualitativeRecord[] = [
  {
    prompt_id: 81, model_names: 'gpt-3.5-turbo vs claude-v1', reasoning_text: 'reasoning one', word_count_diff: 10,
    human_winner: 'A', ai_winner: 'A', prompt_text: 'Verified prompt one', answer_a_text: 'Verified answer A one', answer_b_text: 'Verified answer B one',
    answer_a_model: 'gpt-3.5-turbo', answer_b_model: 'claude-v1', provenance_status: 'VERIFIED',
  },
  {
    prompt_id: 82, model_names: 'gpt-4 vs vicuna-13b', reasoning_text: 'reasoning two', word_count_diff: -20,
    human_winner: 'B', ai_winner: 'A', prompt_text: 'Verified prompt two', answer_a_text: 'Verified answer A two', answer_b_text: 'Verified answer B two',
    answer_a_model: 'gpt-4', answer_b_model: 'vicuna-13b', provenance_status: 'VERIFIED',
  },
];

describe('QualitativeExplorerPage provenance display', () => {
  beforeEach(() => {
    useQualitativeBucket.mockReturnValue({ data: records, loading: false, error: null, refetch: vi.fn() });
  });

  it('renders exact verified prompt and answer text for selected cases', () => {
    render(<ThemeProvider><JudgeProvider><QualitativeExplorerPage /></JudgeProvider></ThemeProvider>);
    expect(screen.getByText('Verified prompt one')).toBeInTheDocument();
    expect(screen.getByText('Verified answer A one')).toBeInTheDocument();
    expect(screen.getByText('Verified answer B one')).toBeInTheDocument();
    expect(screen.queryByText('Provenance unavailable; prompt text is not displayed.')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Prompt #82/i }));
    expect(screen.getByText('Verified prompt two')).toBeInTheDocument();
    expect(screen.getByText('Verified answer A two')).toBeInTheDocument();
    expect(screen.getByText('Verified answer B two')).toBeInTheDocument();
  });
});
