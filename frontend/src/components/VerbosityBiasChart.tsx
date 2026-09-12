import React, { useState, useMemo } from 'react';
import type { VerbosityDataPoint } from '../api/types';
import { useTheme } from '../context/ThemeContext';
import {
  ComposedChart,
  Scatter,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts';

interface Props {
  data: VerbosityDataPoint[];
  loading: boolean;
  error: string | null;
}

/**
 * Dynamically computes OLS linear regression parameters (alpha, beta, R^2)
 * and Spearman rank correlation coefficient (rho) from empirical verbosity data points.
 */
function computeRegressionStats(points: VerbosityDataPoint[]) {
  if (!points || points.length === 0) {
    return null;
  }

  const n = points.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;

  for (let i = 0; i < n; i++) {
    const x = points[i].word_count_diff;
    const y = points[i].llm_verdict;
    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumX2 += x * x;
    sumY2 += y * y;
  }

  const meanX = sumX / n;
  const meanY = sumY / n;

  const denom = sumX2 - n * meanX * meanX;
  const beta = denom !== 0 ? (sumXY - n * meanX * meanY) / denom : 0;
  const alpha = meanY - beta * meanX;

  // Pearson r & R^2 calculation
  const numR = sumXY - n * meanX * meanY;
  const denomR = Math.sqrt(Math.max(0, (sumX2 - n * meanX * meanX) * (sumY2 - n * meanY * meanY)));
  const pearsonR = denomR !== 0 ? numR / denomR : 0;
  const r2 = pearsonR * pearsonR;

  // Spearman rank correlation (rho) calculation
  const getRanks = (arr: number[]) => {
    const sorted = arr.map((v, i) => ({ v, i })).sort((a, b) => a.v - b.v);
    const ranks = new Array(n);
    let i = 0;
    while (i < n) {
      let j = i;
      while (j < n - 1 && sorted[j + 1].v === sorted[i].v) {
        j++;
      }
      const rankVal = (i + j + 2) / 2;
      for (let k = i; k <= j; k++) {
        ranks[sorted[k].i] = rankVal;
      }
      i = j + 1;
    }
    return ranks;
  };

  const rx = getRanks(points.map((p) => p.word_count_diff));
  const ry = getRanks(points.map((p) => p.llm_verdict));

  let meanRx = 0, meanRy = 0;
  for (let i = 0; i < n; i++) {
    meanRx += rx[i];
    meanRy += ry[i];
  }
  meanRx /= n;
  meanRy /= n;

  let numRho = 0, denRx = 0, denRy = 0;
  for (let i = 0; i < n; i++) {
    const dx = rx[i] - meanRx;
    const dy = ry[i] - meanRy;
    numRho += dx * dy;
    denRx += dx * dx;
    denRy += dy * dy;
  }

  const denomRho = Math.sqrt(denRx * denRy);
  const rho = denomRho !== 0 ? numRho / denomRho : 0;

  return { beta, alpha, r2, rho };
}

export const VerbosityBiasChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [sampleSize, setSampleSize] = useState<'100' | '250' | 'All'>('250');

  // PostgreSQL numeric CASE expressions can arrive as JSON strings (for example
  // "0.0"). Normalize at the UI boundary so valid telemetry is not treated as
  // NaN by JavaScript arithmetic or verdict comparisons.
  const numericData = useMemo(
    () => (data || [])
      .map((point) => ({
        word_count_diff: Number(point.word_count_diff),
        llm_verdict: Number(point.llm_verdict),
      })),
    [data]
  );
  const finiteData = useMemo(
    () => numericData.filter((point) => Number.isFinite(point.word_count_diff) && Number.isFinite(point.llm_verdict)),
    [numericData]
  );

  const regStats = useMemo(() => computeRegressionStats(numericData), [numericData]);

  const chartData = useMemo(() => {
    if (!finiteData.length || !regStats) return { scatter: [], trend: [] };

    const limit = sampleSize === '100' ? 100 : sampleSize === '250' ? 250 : finiteData.length;
    const scatter = finiteData.slice(0, limit).map((d, i) => ({
      id: i,
      x: d.word_count_diff,
      y: d.llm_verdict,
      outcome:
        d.llm_verdict === 1.0
          ? 'Answer A won'
          : d.llm_verdict === 0.0
          ? 'Answer B won'
          : 'Tie',
    }));

    const { alpha, beta } = regStats;
    const trend = [
      { x: -300, trendY: Math.max(0, Math.min(1, alpha + beta * -300)) },
      { x: 0, trendY: Math.max(0, Math.min(1, alpha)) },
      { x: 300, trendY: Math.max(0, Math.min(1, alpha + beta * 300)) },
    ];

    return { scatter, trend };
  }, [finiteData, sampleSize, regStats]);

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: { x: number; y: number; outcome: string } }> }) => {
    if (active && payload && payload.length && Number.isFinite(payload[0].payload.y)) {
      const dataPoint = payload[0].payload;
      const diff = dataPoint.x;
      const verdict =
        dataPoint.y === 1.0 ? 'Answer A Won' : dataPoint.y === 0.0 ? 'Answer B Won' : 'TIE / Draw';

      return (
        <div className="p-2.5 rounded bg-white dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 text-xs space-y-1 text-neutral-800 dark:text-neutral-200 font-mono shadow-md">
          <p className="font-bold text-neutral-900 dark:text-white">Disparity: {Number.isFinite(diff) ? `${diff > 0 ? '+' : ''}${diff} words` : 'Unavailable'}</p>
          <p className="text-neutral-600 dark:text-neutral-300">Outcome: {verdict}</p>
        </div>
      );
    }
    return null;
  };

  const displayNumber = (value: number | undefined, digits: number, signed = false) => value !== undefined && Number.isFinite(value) ? `${signed && value >= 0 ? '+' : ''}${value.toFixed(digits)}` : 'Unavailable';
  const inflationPct = regStats && Number.isFinite(regStats.beta) ? `${displayNumber(regStats.beta * 100 * 100, 1, true)}% per 100 words` : 'Unavailable';

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-3 font-sans transition-colors duration-150">
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
        <div>
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
            Length Association
          </h4>
          <p className="text-xs text-neutral-600 dark:text-neutral-400">
            {regStats
              ? `OLS fit to coded outcomes: α (${displayNumber(regStats.alpha, 3)}) + β·ΔWC`
              : 'OLS Fit: No telemetry data'}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 font-mono text-xs">
            <span className="text-[11px] text-neutral-500">Sample:</span>
            <select
              value={sampleSize}
              onChange={(e) => setSampleSize(e.target.value as '100' | '250' | 'All')}
              className="text-xs font-mono bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5 text-neutral-800 dark:text-neutral-200 cursor-pointer focus:outline-none"
            >
              <option value="100">100</option>
              <option value="250">250</option>
              <option value="All">All</option>
            </select>
          </div>
          {regStats && (
            <span className="text-[11px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-2 py-0.5 rounded bg-white dark:bg-neutral-900">
              &beta; = {displayNumber(regStats.beta, 6, true)}
            </span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center font-mono text-xs text-neutral-500">
          Loading verbosity telemetry...
        </div>
      ) : error ? (
        <div className="h-64 flex items-center justify-center text-neutral-600 dark:text-neutral-400 text-xs">{error}</div>
      ) : !numericData.length || !regStats ? (
        <div className="h-64 flex flex-col items-center justify-center font-mono text-xs text-neutral-500 space-y-1.5">
          <p className="font-semibold text-neutral-700 dark:text-neutral-300">No telemetry data available</p>
          <p className="text-neutral-500 text-[11px]">No verbosity comparison samples found for this judge model.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="h-72 w-full" role="img" aria-label="Length association: each dot is an observed decision at its exact word-count difference. B won is coded 0, Tie 0.5, and A won 1. Dotted OLS fit summarizes these numeric codes, not a predicted win probability. The vertical zero line means equal answer lengths.">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 14, right: 14, left: 0, bottom: 25 }}>
                <Legend verticalAlign="top" align="right" height={30} iconSize={9} wrapperStyle={{ fontSize: 11, color: isDark ? '#d4d4d4' : '#525252' }} />
                {[0, 0.5, 1].map((outcome) => <ReferenceLine key={outcome} y={outcome} stroke={isDark ? '#292d32' : '#e2e5e9'} />)}
                <XAxis type="number" dataKey="x" stroke={isDark ? '#a3a3a3' : '#737373'} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickMargin={8} minTickGap={30} domain={[-300, 300]} label={{ value: 'Word-count difference (A − B)', position: 'bottom', offset: 8, fill: isDark ? '#a3a3a3' : '#525252', fontSize: 11 }} />
                <YAxis type="number" dataKey="y" width={84} axisLine={false} tickLine={false} tickMargin={8} tick={{ fontSize: 11, fill: isDark ? '#d4d4d4' : '#404040' }} domain={[-0.12, 1.12]} ticks={[0, 0.5, 1]} tickFormatter={(value) => value === 1 ? 'A won' : value === 0 ? 'B won' : 'Tie'} />
                <ReferenceLine x={0} stroke={isDark ? '#525963' : '#a3aab3'} strokeDasharray="3 6" />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: isDark ? '#737373' : '#a3a3a3', strokeDasharray: '3 3' }} />
                {/* Keep each observation, including repeated x values and outcomes. */}
                <Scatter name="Observed decisions" data={chartData.scatter} dataKey="y" fill={isDark ? '#73a6c8' : '#3779a5'} isAnimationActive={false} shape={({ cx, cy }: { cx?: number; cy?: number }) => <circle cx={cx} cy={cy} r={3} fill={isDark ? '#73a6c8' : '#3779a5'} fillOpacity={0.5} />} />
                {Number.isFinite(regStats.alpha) && Number.isFinite(regStats.beta) && <Line
                  type="monotone"
                  data={chartData.trend}
                  dataKey="trendY"
                  stroke={isDark ? '#a6b5c4' : '#576b80'}
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  name="OLS · coded outcomes"
                />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-1 text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">
            <p className="flex flex-wrap justify-between gap-x-4 gap-y-1"><span>← Answer B longer</span><span>0 = equal lengths</span><span>Answer A longer →</span></p>
          </div>

          <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 font-mono flex justify-between">
            <span>Spearman Rank Correlation: <strong className="text-neutral-900 dark:text-neutral-200">&rho; = {displayNumber(regStats.rho, 4, true)}</strong></span>
            <span>Inflation: <strong className="text-[#38bdf8] font-semibold">{inflationPct}</strong></span>
          </div>
        </div>
      )}
    </div>
  );
};
