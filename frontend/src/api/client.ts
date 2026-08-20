import axios from 'axios';
import { useState, useEffect, useCallback } from 'react';
import { isControlledResultsResponse } from './types';
import type {
  LeaderboardItem,
  BiasStatsResponse,
  QualitativeRecord,
  QualitativeBucket,
  EvaluateRequest,
  EvaluateResponse,
  CalibratedEvaluateRequest,
  CalibratedEvaluateResponse,
  EnsembleEvaluateRequest,
  EnsembleEvaluateResponse,
  ConsistencyStatsResponse,
  DatasetCountResponse,
  InterJudgeReliability,
  SelfPreferenceResponse,
  MacroBenchmarkResponse,
  ControlledResultsResponse,
} from './types';

/**
 * Resolve backend API base URL.
 * Prioritizes environment variables (VITE_API_BASE_URL or VITE_API_URL) for production deployments.
 * Falls back to 'http://localhost:8000' strictly for local standalone development environments.
 */
const getBaseURL = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL;
  if (envUrl) {
    return envUrl;
  }
  // Local development fallback to FastAPI dev server port 8000
  return 'http://localhost:8000';
};

// Axios instance targeting backend FastAPI server
export const apiClient = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 180,000ms (3 minutes) base timeout
});

/**
 * Fetch unified leaderboard data (Bradley-Terry + Residual Neutralized scores)
 */
export async function getLeaderboard(judgeModel?: string, forceRecalculate = false): Promise<LeaderboardItem[]> {
  const response = await apiClient.get<LeaderboardItem[]>('/api/leaderboard', {
    params: {
      ...(judgeModel ? { judge_model: judgeModel } : {}),
      ...(forceRecalculate ? { force_recalculate: true } : {}),
    },
  });
  return response.data;
}

/**
 * Trigger on-demand recalculation of Bradley-Terry MLE and OLS Length Neutralization
 */
export async function calculateLeaderboard(judgeModel: string): Promise<LeaderboardItem[]> {
  const response = await apiClient.post<LeaderboardItem[]>('/api/leaderboard/calculate', {
    judge_model: judgeModel,
  });
  return response.data;
}

/**
 * Fetch exact count of human_preferences benchmark records from PostgreSQL
 */
export async function getDatasetCount(): Promise<DatasetCountResponse> {
  const response = await apiClient.get<DatasetCountResponse>('/api/stats/dataset-count');
  return response.data;
}

/** Controlled-only route. It never falls back to legacy, sandbox, or mock data. */
export async function getControlledResults(): Promise<ControlledResultsResponse> {
  const response = await apiClient.get<ControlledResultsResponse>('/api/controlled/results');
  if (!isControlledResultsResponse(response.data)) {
    throw new Error('Controlled evidence response failed its scientific contract validation.');
  }
  return response.data;
}

export function useControlledResults() {
  const [data, setData] = useState<ControlledResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetch = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await getControlledResults()); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Failed to fetch controlled evidence status'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { fetch(); }, [fetch]);
  return { data, loading, error, refetch: fetch };
}

/**
 * Fetch raw bias data for telemetry & visualization (verbosity + position counts)
 */
export async function getBiasStats(judgeModel?: string): Promise<BiasStatsResponse> {
  const response = await apiClient.get<BiasStatsResponse>('/api/stats/bias', {
    params: judgeModel ? { judge_model: judgeModel } : undefined,
  });
  return response.data;
}

/**
 * Fetch stratified qualitative evaluation records by bucket category
 */
export async function getQualitativeBucket(
  bucket: QualitativeBucket,
  judgeModel?: string
): Promise<QualitativeRecord[]> {
  const response = await apiClient.get<QualitativeRecord[]>(`/api/qualitative/${bucket}`, {
    params: judgeModel ? { judge_model: judgeModel } : undefined,
  });
  return response.data;
}

/**
 * Execute live G-EVAL evaluation comparing Answer A vs Answer B
 */
export async function executeLiveEvaluation(
  payload: EvaluateRequest
): Promise<EvaluateResponse> {
  const m = (payload.model_name || '').toLowerCase();
  const isLocal = m.includes('llama') || m.includes('ollama') || m.includes('local');
  const timeoutMs = isLocal ? 180000 : 120000; // 3 mins for local single-pass, 2 mins for cloud
  const response = await apiClient.post<EvaluateResponse>('/api/evaluate', payload, { timeout: timeoutMs });
  return response.data;
}

/**
 * Execute active real-time in-flight bias mitigated evaluation (Dual A/B Swap)
 */
export async function executeCalibratedEvaluation(
  payload: CalibratedEvaluateRequest
): Promise<CalibratedEvaluateResponse> {
  const m = (payload.model_name || '').toLowerCase();
  const isLocal = m.includes('llama') || m.includes('ollama') || m.includes('local');
  const timeoutMs = isLocal ? 240000 : 180000; // 4 mins for local Dual A/B Swap, 3 mins for cloud
  const response = await apiClient.post<CalibratedEvaluateResponse>('/api/evaluate/calibrated', payload, { timeout: timeoutMs });
  return response.data;
}

/**
 * Execute concurrent multi-judge ensemble voting evaluation
 */
export async function executeEnsembleEvaluation(
  payload: EnsembleEvaluateRequest
): Promise<EnsembleEvaluateResponse> {
  const timeoutMs = 300000; // 5 mins timeout for multi-model ensemble
  try {
    const response = await apiClient.post<EnsembleEvaluateResponse>('/api/evaluate/ensemble', payload, { timeout: timeoutMs });
    return response.data;
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error('[Ensemble API Error Details]', {
        status: err.response?.status,
        statusText: err.response?.statusText,
        data: err.response?.data,
        message: err.message,
        payloadSent: payload,
      });
      const detailMsg = err.response?.data?.detail || err.message;
      throw new Error(typeof detailMsg === 'string' ? detailMsg : JSON.stringify(detailMsg));
    }
    console.error('[Ensemble API Non-Axios Error]', err);
    throw err;
  }
}


// ── Custom React Hooks for UI Components ──────────────────────────────────────

export function useDatasetCount() {
  const [count, setCount] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getDatasetCount();
      setCount(res.count);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch dataset count';
      setError(msg);
      setCount(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { count, loading, error, refetch: fetch };
}

export function useLeaderboard(judgeModel?: string) {
  const [data, setData] = useState<LeaderboardItem[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async (forceRecalculate = false) => {
    setLoading(true);
    setError(null);
    try {
      const result = forceRecalculate
        ? await calculateLeaderboard(judgeModel || 'gpt-4o-mini')
        : await getLeaderboard(judgeModel);
      setData(result);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to fetch leaderboard data');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [judgeModel]);

  useEffect(() => {
    fetch(false);
  }, [fetch]);

  return { data, loading, error, refetch: () => fetch(false), recalculate: () => fetch(true) };
}

export function useBiasStats(judgeModel?: string) {
  const [data, setData] = useState<BiasStatsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getBiasStats(judgeModel);
      setData(result);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to fetch bias diagnostics data');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [judgeModel]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useQualitativeBucket(bucket: QualitativeBucket, judgeModel?: string) {
  const [data, setData] = useState<QualitativeRecord[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getQualitativeBucket(bucket, judgeModel);
      setData(result);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to fetch qualitative records');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [bucket, judgeModel]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

/**
 * Fetch multi-turn logical consistency and inter-judge reliability stats
 */
export async function getConsistencyStats(judgeModel?: string): Promise<ConsistencyStatsResponse> {
  const response = await apiClient.get<ConsistencyStatsResponse>('/api/consistency', {
    params: judgeModel ? { judge_model: judgeModel } : undefined,
  });
  return response.data;
}

export function useConsistencyStats(judgeModel?: string) {
  const [data, setData] = useState<ConsistencyStatsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getConsistencyStats(judgeModel);
      setData(result);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to fetch consistency statistics');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [judgeModel]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

/**
 * Fetch dynamic Inter-Judge Cohen's Kappa score comparing two judge models
 */
export async function getInterJudgeKappa(modelA: string, modelB: string): Promise<InterJudgeReliability> {
  const response = await apiClient.get<InterJudgeReliability>('/api/stats/inter-judge-kappa', {
    params: { model_a: modelA, model_b: modelB },
  });
  return response.data;
}

export function useInterJudgeKappa(modelA: string, modelB: string) {
  const [data, setData] = useState<InterJudgeReliability | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!modelA || !modelB) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getInterJudgeKappa(modelA, modelB);
      setData(res);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to compute inter-judge kappa');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [modelA, modelB]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

/**
 * Fetch Self-Preference Bias statistics for a given judge model
 */
export async function getSelfPreferenceStats(judgeModel?: string): Promise<SelfPreferenceResponse> {
  const response = await apiClient.get<SelfPreferenceResponse>('/api/stats/self-preference', {
    params: judgeModel ? { judge_model: judgeModel } : undefined,
  });
  return response.data;
}

export function useSelfPreferenceStats(judgeModel?: string) {
  const [data, setData] = useState<SelfPreferenceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getSelfPreferenceStats(judgeModel);
      setData(result);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to fetch self-preference statistics');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [judgeModel]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

/**
 * Fetch aggregate macro benchmark synthesis stats (Before vs After Mitigation)
 */
export async function getMacroBenchmark(judgeModel?: string): Promise<MacroBenchmarkResponse> {
  const response = await apiClient.get<MacroBenchmarkResponse>('/api/stats/macro-benchmark', {
    params: judgeModel ? { judge_model: judgeModel } : undefined,
  });
  return response.data;
}

export function useMacroBenchmark(judgeModel?: string) {
  const [data, setData] = useState<MacroBenchmarkResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getMacroBenchmark(judgeModel);
      setData(result);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to fetch macro benchmark stats');
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [judgeModel]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}



