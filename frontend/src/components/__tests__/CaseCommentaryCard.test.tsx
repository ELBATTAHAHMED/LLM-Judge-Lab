import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it } from 'vitest';
import { CaseCommentaryCard } from '../CaseCommentaryCard';
import type { QualitativeRecord } from '../../api/types';

const record: QualitativeRecord = {
  prompt_id: 7,
  reasoning_text: 'historical reasoning',
  word_count_diff: 42,
  human_winner: 'A',
  ai_winner: 'B',
  model_names: 'gpt-4o-mini vs claude',
};

describe('CaseCommentaryCard exploratory claim boundaries', () => {
  it('frames a verbosity case as historical rather than systematic evidence', () => {
    render(<CaseCommentaryCard bucket="verbosity" record={record} />);

    expect(screen.getByText(/selected historical case is consistent with a length-associated preference/i)).toBeInTheDocument();
    expect(screen.getByText(/not controlled evidence of a systematic length effect/i)).toBeInTheDocument();
    expect(screen.queryByText(/systematically inflated the judge's score/i)).not.toBeInTheDocument();
  });

  it('frames a position case as a case-specific observation requiring controlled RQ3', () => {
    render(<CaseCommentaryCard bucket="position_bias" record={record} />);

    expect(screen.getByText(/selected historical case favored the answer shown in position b/i)).toBeInTheDocument();
    expect(screen.getByText(/controlled rq3 is required for presentation-order sensitivity inference/i)).toBeInTheDocument();
    expect(screen.queryByText(/position b exhibits selection bias/i)).not.toBeInTheDocument();
  });
});
