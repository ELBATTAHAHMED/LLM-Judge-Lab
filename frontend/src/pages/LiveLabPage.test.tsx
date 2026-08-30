import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it, vi } from 'vitest';

const liveState = vi.hoisted(() => ({ enabled: false }));
const liveApi = vi.hoisted(() => ({
  getStatus: vi.fn(),
  standard: vi.fn(),
  calibrated: vi.fn(),
  ensemble: vi.fn(),
}));

vi.mock('../api/client', () => ({
  getLiveSandboxStatus: () => {
    liveApi.getStatus();
    return Promise.resolve({ enabled: liveState.enabled });
  },
  executeLiveEvaluation: liveApi.standard,
  executeCalibratedEvaluation: liveApi.calibrated,
  executeEnsembleEvaluation: liveApi.ensemble,
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
    expect(screen.getByText(/manual exploratory evaluation/i)).toBeInTheDocument();
    expect(liveApi.getStatus).toHaveBeenCalledTimes(1);
    expect(liveApi.standard).not.toHaveBeenCalled();
    expect(liveApi.calibrated).not.toHaveBeenCalled();
    expect(liveApi.ensemble).not.toHaveBeenCalled();
  });

  it('keeps the normal live workflow available when the server gate is on', async () => {
    liveState.enabled = true;
    render(<LiveLabPage />);

    expect(await screen.findByText('Real provider execution is enabled for this local server.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run Standard G-EVAL Evaluation Trial' })).toBeEnabled();
    expect(liveApi.standard).not.toHaveBeenCalled();
    expect(liveApi.calibrated).not.toHaveBeenCalled();
    expect(liveApi.ensemble).not.toHaveBeenCalled();
  });
});
