import React from 'react';
import type { FormatBiasData } from '../api/types';
import { useTheme } from '../context/ThemeContext';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface Props {
  data: FormatBiasData | null;
  loading: boolean;
  error: string | null;
}

export const FormatBiasChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const hasData = data?.markdown_chosen !== null && data?.plain_text_chosen !== null;
  const chartData = hasData && data
    ? [
        { name: 'Markdown-Heavy', count: data.markdown_chosen, color: '#0d9488' },
        { name: 'Plain Text', count: data.plain_text_chosen, color: isDark ? '#404040' : '#737373' },
      ]
    : [];

  const total = chartData.reduce((sum, item) => sum + (item.count ?? 0), 0);

  const pValueFormatted = typeof data?.p_value === 'number'
    ? data.p_value < 0.001
      ? 'p < 0.001'
      : `p = ${data.p_value.toFixed(4)}`
    : '';

  const chi2Formatted = typeof data?.chi2_stat === 'number'
    ? data.chi2_stat.toFixed(2)
    : '0.00';

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
      <div className="space-y-3 flex-1 flex flex-col justify-between">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
              Exploratory Formatting Association
            </h4>
            <p className="text-xs text-neutral-500">
              Selection frequency when candidates differ in Markdown formatting
            </p>
          </div>
          {hasData && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-teal-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-teal-400 dark:border-neutral-700 shadow-none ring-0">
              &chi;&sup2; = {chi2Formatted} ({pValueFormatted || 'p-val N/A'})
            </span>
          )}
        </div>


        {loading ? (
          <div className="h-64 flex items-center justify-center font-mono text-xs text-neutral-500 flex-1">
            Loading exploratory formatting telemetry...
          </div>
        ) : error ? (
          <div className="h-64 flex items-center justify-center text-neutral-600 dark:text-neutral-400 text-xs flex-1">
            {error}
          </div>
        ) : !hasData ? (
          <div className="h-64 flex items-center justify-center text-neutral-500 text-xs flex-1">No eligible exploratory formatting observations.</div>
        ) : (
          <div className="space-y-3 flex-1 flex flex-col justify-between">
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 15, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#262626' : '#e5e5e5'} />
                  <XAxis dataKey="name" stroke="#a3a3a3" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#a3a3a3" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      background: isDark ? '#0a0a0a' : '#ffffff',
                      borderColor: isDark ? '#404040' : '#e5e5e5',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontFamily: 'monospace',
                      boxShadow: isDark ? 'none' : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                    }}
                    itemStyle={{ color: isDark ? '#e5e5e5' : '#171717' }}
                    labelStyle={{ color: isDark ? '#ffffff' : '#171717', fontWeight: 600 }}
                    formatter={(val: unknown) => [`${val} decisions`, 'Count']}
                  />
                  <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.color}
                        stroke={isDark ? '#404040' : '#d4d4d4'}
                        strokeWidth={1}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400">
              <strong className="text-neutral-900 dark:text-neutral-200">Exploratory formatting association:</strong> this historical heuristic is not the final controlled RQ5 experiment. See Controlled Experiments for the frozen Controlled Presentation-Format Effect.
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-center text-xs font-mono pt-3">
        {chartData.map((p) => (
          <div key={p.name} className="p-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
            <p className="text-neutral-500 text-[11px]">{p.name}</p>
            <p className="font-semibold text-neutral-900 dark:text-neutral-200 text-sm">{p.count}</p>
            <p className="text-[10px] text-neutral-500">
              {total > 0 && p.count !== null ? `${((p.count / total) * 100).toFixed(1)}%` : 'N/A'}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
