import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  apiClient,
  executeCalibratedEvaluation,
  executeEnsembleEvaluation,
  executeLiveEvaluation,
  getLiveSandboxStatus,
} from './client';

afterEach(() => vi.restoreAllMocks());

describe('manual Live Sandbox client flow', () => {
  it('reads the secret-free local enablement status', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { provider_calls_enabled: true } } as never);

    await expect(getLiveSandboxStatus()).resolves.toEqual({ provider_calls_enabled: true });
    expect(get).toHaveBeenCalledWith('/api/live-sandbox/status');
  });

  it('sends the selected model, answers, and protocol to the existing live endpoints', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} } as never);
    const token = 'test-operator-token';

    await executeLiveEvaluation({ prompt: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini' }, token);
    await executeCalibratedEvaluation({ question: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini', mitigation_strategy: 'dual_ab' }, token);
    await executeEnsembleEvaluation({ question: 'question', answer_a: 'A', answer_b: 'B', judge_models: ['gpt-4o-mini'], mitigation_strategy: 'none' }, token);

    expect(post).toHaveBeenNthCalledWith(1, '/api/evaluate', expect.objectContaining({ prompt: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini' }), expect.objectContaining({ headers: { 'X-Live-Sandbox-Token': token } }));
    expect(post).toHaveBeenNthCalledWith(2, '/api/evaluate/calibrated', expect.objectContaining({ question: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini', mitigation_strategy: 'dual_ab' }), expect.objectContaining({ headers: { 'X-Live-Sandbox-Token': token } }));
    expect(post).toHaveBeenNthCalledWith(3, '/api/evaluate/ensemble', expect.objectContaining({ question: 'question', answer_a: 'A', answer_b: 'B', judge_models: ['gpt-4o-mini'], mitigation_strategy: 'none' }), expect.objectContaining({ headers: { 'X-Live-Sandbox-Token': token } }));
  });
});
