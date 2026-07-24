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
} from './types';

// Axios instance targeting backend FastAPI dev server
export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
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
  const response = await apiClient.post<EvaluateResponse>('/api/evaluate', payload);
  return response.data;
}

/**
 * Execute active real-time in-flight bias mitigated evaluation (Dual A/B Swap)
 */
export async function executeCalibratedEvaluation(
  payload: CalibratedEvaluateRequest
): Promise<CalibratedEvaluateResponse> {
  const response = await apiClient.post<CalibratedEvaluateResponse>('/api/evaluate/calibrated', payload);
  return response.data;
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
