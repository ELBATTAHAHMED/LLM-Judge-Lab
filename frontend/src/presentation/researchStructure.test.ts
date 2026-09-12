import { describe, expect, it } from 'vitest';
import {
  DETAILED_RQ_ORDER,
  MAIN_QUESTION_PRESENTATION,
  MITIGATION_BY_ID,
  RESEARCH_QUESTION_BY_ID,
} from './researchStructure';

describe('research presentation structure', () => {
  it('maps the three main questions to the frozen internal RQ identifiers', () => {
    expect(MAIN_QUESTION_PRESENTATION).toEqual([
      expect.objectContaining({ id: 'MAIN_Q1', internalRqIds: ['RQ1'] }),
      expect.objectContaining({ id: 'MAIN_Q2', internalRqIds: ['RQ2', 'RQ3'] }),
      expect.objectContaining({ id: 'MAIN_Q3', internalRqIds: ['RQ7'] }),
    ]);
  });

  it('keeps supporting analyses classified separately from the three main questions', () => {
    expect(RESEARCH_QUESTION_BY_ID.RQ4).toMatchObject({ role: 'SECONDARY', parentMainQuestion: null });
    expect(RESEARCH_QUESTION_BY_ID.RQ5).toMatchObject({ role: 'SECONDARY', parentMainQuestion: null });
    expect(RESEARCH_QUESTION_BY_ID.RQ6).toMatchObject({ role: 'EXPLORATORY', parentMainQuestion: null });
  });

  it('preserves RQ7 primary and Multi-Judge secondary/exploratory presentation roles', () => {
    expect(RESEARCH_QUESTION_BY_ID.RQ7).toMatchObject({ role: 'MAIN', parentMainQuestion: 'MAIN_Q3', mitigationRole: 'PRIMARY' });
    expect(MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS).toMatchObject({ role: 'SECONDARY', internalRqId: 'RQ7', parentMainQuestion: 'MAIN_Q3', exploratory: true });
  });

  it('retains the detailed RQ1–RQ7 navigation order', () => {
    expect(DETAILED_RQ_ORDER).toEqual(['RQ1', 'RQ2', 'RQ3', 'RQ4', 'RQ5', 'RQ6', 'RQ7']);
  });
});
