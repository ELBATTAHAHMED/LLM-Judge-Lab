import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  apiClient,
  executeCalibratedEvaluation,
  executeEnsembleEvaluation,
  executeLiveEvaluation,
} from './client';

afterEach(() => vi.restoreAllMocks());

describe('manual Live Sandbox client flow', () => {
  it('sends the selected model, answers, and protocol to the existing live endpoints', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} } as never);

    await executeLiveEvaluation({ prompt: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini' });
    await executeCalibratedEvaluation({ question: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini', mitigation_strategy: 'dual_ab' });
    await executeEnsembleEvaluation({ question: 'question', answer_a: 'A', answer_b: 'B', judge_models: ['gpt-4o-mini'], mitigation_strategy: 'none' });

    expect(post).toHaveBeenNthCalledWith(1, '/api/evaluate', expect.objectContaining({ prompt: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini' }), { timeout: 120000 });
    expect(post).toHaveBeenNthCalledWith(2, '/api/evaluate/calibrated', expect.objectContaining({ question: 'question', answer_a: 'A', answer_b: 'B', model_name: 'gpt-4o-mini', mitigation_strategy: 'dual_ab' }), { timeout: 180000 });
    expect(post).toHaveBeenNthCalledWith(3, '/api/evaluate/ensemble', expect.objectContaining({ question: 'question', answer_a: 'A', answer_b: 'B', judge_models: ['gpt-4o-mini'], mitigation_strategy: 'none' }), { timeout: 300000 });
  });
});
