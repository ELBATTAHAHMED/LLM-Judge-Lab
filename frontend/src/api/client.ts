import axios from 'axios';
import { useState, useEffect, useCallback } from 'react';
import type {
  LeaderboardItem,
  BiasStatsResponse,
  QualitativeRecord,
  QualitativeBucket,
  EvaluateRequest,
  EvaluateResponse,
  CalibratedEvaluateRequest,
  CalibratedEvaluateResponse,
  BatchRunRequest,
  PerturbationRunRequest,
  StochasticRunRequest,
  ExperimentJobStatus,
} from './types';

// Axios instance targeting backend FastAPI dev server
export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 180,000ms (3 minutes) base timeout
});

/**
 * Fetch unified leaderboard data (Bradley-Terry + Residual Neutralized scores)
 */
export async function getLeaderboard(): Promise<LeaderboardItem[]> {
  const response = await apiClient.get<LeaderboardItem[]>('/api/leaderboard');
  return response.data;
}

/**
 * Fetch raw bias data for telemetry & visualization (verbosity + position counts)
 */
export async function getBiasStats(): Promise<BiasStatsResponse> {
  const response = await apiClient.get<BiasStatsResponse>('/api/stats/bias');
  return response.data;
}

/**
 * Fetch stratified qualitative evaluation records by bucket category
 */
export async function getQualitativeBucket(
  bucket: QualitativeBucket
): Promise<QualitativeRecord[]> {
  const response = await apiClient.get<QualitativeRecord[]>(`/api/qualitative/${bucket}`);
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

export async function triggerBatchRun(payload: BatchRunRequest): Promise<{ status: string; job_id: string; message: string }> {
  const res = await apiClient.post('/api/experiments/run-batch', payload);
  return res.data;
}

export async function triggerPerturbationRun(payload: PerturbationRunRequest): Promise<{ status: string; job_id: string; message: string }> {
  const res = await apiClient.post('/api/experiments/perturbations', payload);
  return res.data;
}

export async function triggerStochasticRun(payload: StochasticRunRequest): Promise<{ status: string; job_id: string; message: string }> {
  const res = await apiClient.post('/api/experiments/stochastic', payload);
  return res.data;
}

export async function getJobStatus(jobId: string): Promise<ExperimentJobStatus> {
  const res = await apiClient.get<ExperimentJobStatus>(`/api/experiments/status/${jobId}`);
  return res.data;
}

export async function fetchReportSummary(): Promise<any> {
  const res = await apiClient.get('/api/report/summary');
  return res.data;
}

// ── Custom React Hooks for UI Components ──────────────────────────────────────

export function useLeaderboard() {
  const [data, setData] = useState<LeaderboardItem[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getLeaderboard();
      setData(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to fetch leaderboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useBiasStats() {
  const [data, setData] = useState<BiasStatsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getBiasStats();
      setData(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to fetch bias diagnostics data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useQualitativeBucket(bucket: QualitativeBucket) {
  const [data, setData] = useState<QualitativeRecord[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getQualitativeBucket(bucket);
      setData(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to fetch qualitative records');
    } finally {
      setLoading(false);
    }
  }, [bucket]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}
