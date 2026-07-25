import { useState, useEffect } from 'react';
import type { ExperimentJobStatus } from '../api/types';
import { getJobStatus } from '../api/client';

export function useExperimentProgress(jobId: string | null) {
  const [jobStatus, setJobStatus] = useState<ExperimentJobStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJobStatus(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    // Set up SSE EventSource connection
    const sseUrl = `http://localhost:8000/api/experiments/stream/${jobId}`;
    let eventSource: EventSource | null = new EventSource(sseUrl);
    let pollInterval: ReturnType<typeof setInterval> | null = null;

    eventSource.onmessage = (event) => {
      try {
        const data: ExperimentJobStatus = JSON.parse(event.data);
        setJobStatus(data);
        setLoading(false);

        if (data.status === 'completed' || data.status === 'failed') {
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE Connection error, falling back to HTTP short polling...', err);
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      // Short polling fallback
      pollInterval = setInterval(async () => {
        try {
          const statusData = await getJobStatus(jobId);
          setJobStatus(statusData);
          setLoading(false);

          if (statusData.status === 'completed' || statusData.status === 'failed') {
            if (pollInterval) clearInterval(pollInterval);
          }
        } catch (pollErr: any) {
          setError(pollErr?.message || 'Failed to fetch job status');
          if (pollInterval) clearInterval(pollInterval);
        }
      }, 500);
    };

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [jobId]);

  return { jobStatus, loading, error };
}
