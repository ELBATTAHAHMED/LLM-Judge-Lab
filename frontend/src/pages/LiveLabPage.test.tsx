import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it, vi } from 'vitest';

const liveState = vi.hoisted(() => ({ enabled: false }));

vi.mock('../api/client', () => ({
  getLiveSandboxStatus: () => Promise.resolve({ enabled: liveState.enabled }),
  executeLiveEvaluation: vi.fn(),
  executeCalibratedEvaluation: vi.fn(),
  executeEnsembleEvaluation: vi.fn(),
}));

vi.mock('../context/JudgeContext', () => ({
  useJudge: () => ({ judgeModel: 'gpt-4o-mini' }),
}));

import { LiveLabPage } from './LiveLabPage';

describe('LiveLabPage server-configured execution state', () => {
  it('keeps the sandbox visible while disabling submission when the server gate is off', async () => {
    liveState.enabled = false;
    render(<LiveLabPage />);

    expect(await screen.findByText('Real provider execution is disabled by this server configuration.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Live execution disabled by server' })).toBeDisabled();
  });

  it('keeps the normal live workflow available when the server gate is on', async () => {
    liveState.enabled = true;
    render(<LiveLabPage />);

    expect(await screen.findByText('Real provider execution is enabled for this local server.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run Standard G-EVAL Evaluation Trial' })).toBeEnabled();
  });
});
