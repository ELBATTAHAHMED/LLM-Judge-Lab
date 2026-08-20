import React from 'react';
import type { PositionData } from '../api/types';
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
  data: PositionData | null;
  loading: boolean;
  error: string | null;
}

export const PositionBiasChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const hasData = data?.position_a !== null && data?.position_b !== null && data?.tie !== null;
  const chartData = hasData && data
    ? [
        { name: 'Position A', count: data.position_a, color: '#737373' },
        { name: 'Position B', count: data.position_b, color: '#818cf8' }, // Subtle desaturated indigo highlight
        { name: 'Tie / Draw', count: data.tie, color: isDark ? '#262626' : '#525252' },
      ]
    : [];

  const posA = data?.position_a ?? 0;
  const posB = data?.position_b ?? 0;
  const binaryTotal = posA + posB;
  const chi2Stat = binaryTotal > 0 ? Math.pow(posA - posB, 2) / binaryTotal : 0;
  const preferredPos = posB >= posA ? 'Position B' : 'Position A';

  const total = chartData.reduce((sum, item) => sum + (item.count || 0), 0);


  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
      <div className="space-y-3 flex-1 flex flex-col justify-between">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
              Slot-Win Distribution
            </h4>
            <p className="text-xs text-neutral-500">
              Selection frequency by physical choice order in prompt
            </p>
          </div>
          {hasData && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-neutral-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-neutral-400 dark:border-neutral-700 shadow-none ring-0">
              &chi;&sup2; = {chi2Stat.toFixed(2)} (df=1)
            </span>
          )}
        </div>

        {loading ? (
          <div className="h-64 flex items-center justify-center font-mono text-xs text-neutral-500 flex-1">
            Loading position distribution...
          </div>
        ) : error ? (
          <div className="h-64 flex items-center justify-center text-neutral-600 dark:text-neutral-400 text-xs flex-1">{error}</div>
        ) : !hasData ? (
          <div className="h-64 flex items-center justify-center text-neutral-500 text-xs flex-1">No eligible slot-win observations.</div>
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
              <strong className="text-neutral-900 dark:text-neutral-200">Slot-win imbalance:</strong> this aggregate count is not the controlled paired decisive flip rate. It currently has more selections in <strong className="text-neutral-900 dark:text-neutral-200">{preferredPos}</strong>.
            </div>
          </div>
        )}
      </div>


      <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono pt-3">
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
