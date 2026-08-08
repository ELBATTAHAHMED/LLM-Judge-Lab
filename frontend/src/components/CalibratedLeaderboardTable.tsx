import React, { useState, useMemo } from 'react';
import type { LeaderboardItem } from '../api/types';
import { ArrowUpDown, ArrowUp, ArrowDown, RefreshCw, Download, Award, Activity, Minus, RotateCcw } from 'lucide-react';
import { ModelIcon, formatModelName } from './ModelIcons';

interface Props {
  data: LeaderboardItem[] | null;
  loading: boolean;
  error: string | null;
  onRefresh?: () => void;
  onRecalculate?: () => void;
}

type ViewMode = 'calibrated' | 'raw';
type SortColumn = 'bt_score' | 'raw_win_rate' | 'neutralized_score' | 'model';
type SortDirection = 'asc' | 'desc';
type ProviderFilter = 'All' | 'OpenAI' | 'Anthropic' | 'Open-Source';

export const CalibratedLeaderboardTable: React.FC<Props> = ({
  data,
  loading,
  error,
  onRefresh,
  onRecalculate,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('calibrated');
  const [sortColumn, setSortColumn] = useState<SortColumn>('bt_score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [providerFilter, setProviderFilter] = useState<ProviderFilter>('All');

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const sortedData = useMemo(() => {
    if (!data) return [];
    const items = [...data];
    items.sort((a, b) => {
      let valA = a[sortColumn];
      let valB = b[sortColumn];
      if (typeof valA === 'string') {
        return sortDirection === 'asc'
          ? (valA as string).localeCompare(valB as string)
          : (valB as string).localeCompare(valA as string);
      }
      return sortDirection === 'asc'
        ? (valA as number) - (valB as number)
        : (valB as number) - (valA as number);
    });
    return items;
  }, [data, sortColumn, sortDirection]);

  const getProvider = (modelName: string) => {
    const name = modelName.toLowerCase();
    if (name.includes('gpt')) return 'OpenAI';
    if (name.includes('claude')) return 'Anthropic';
    return 'Open-Source';
  };

  const filteredData = useMemo(() => {
    if (providerFilter === 'All') return sortedData;
    return sortedData.filter((item) => getProvider(item.model) === providerFilter);
  }, [sortedData, providerFilter]);

  const handleExportCSV = () => {
    if (!filteredData || filteredData.length === 0) return;
    const headers = ['Rank', 'Model', 'Provider', 'Raw Win Rate', 'BT Score', 'Neutralized Score', 'Quality Tier'];
    const rows = filteredData.map((item, idx) => [
      idx + 1,
      `"${item.model}"`,
      `"${getProvider(item.model)}"`,
      (item.raw_win_rate * 100).toFixed(1) + '%',
      item.bt_score.toFixed(5),
      item.neutralized_score.toFixed(5),
      `"${item.quality_tier}"`,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'judgelab_leaderboard_calibrated.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getTierBadge = (tier: string) => {
    const t = (tier || '').toLowerCase();

    if (t.includes('top')) {
      return (
        <div className="flex justify-center">
          <div className="inline-flex items-center gap-1.5 border-l-2 border-rose-800/40 dark:border-rose-500/40 pl-2 py-0.5 font-sans">
            <Award className="w-3.5 h-3.5 text-rose-700/80 dark:text-rose-400/80" />
            <span className="font-mono text-[10px] uppercase tracking-widest font-bold text-rose-900/90 dark:text-rose-300/90">Top Tier</span>
          </div>
        </div>
      );
    }
    if (t.includes('comp')) {
      return (
        <div className="flex justify-center">
          <div className="inline-flex items-center gap-1.5 border-l-2 border-teal-800/40 dark:border-teal-500/30 pl-2 py-0.5 font-sans">
            <Activity className="w-3 h-3 text-teal-700/70 dark:text-teal-400/70" />
            <span className="font-mono text-[10px] uppercase tracking-widest font-medium text-teal-800/80 dark:text-teal-300/80">Competitive</span>
          </div>
        </div>
      );
    }
    return (
      <div className="flex justify-center">
        <div className="inline-flex items-center gap-1.5 border-l-2 border-neutral-300 dark:border-neutral-800 pl-2 py-0.5 font-sans">
          <Minus className="w-3 h-3 text-neutral-400 dark:text-neutral-600" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 dark:text-neutral-500">Below Average</span>
        </div>
      </div>
    );
  };

  const renderSortIndicator = (column: SortColumn) => {
    if (sortColumn !== column) {
      return <ArrowUpDown className="w-3 h-3 text-neutral-400 dark:text-neutral-600 inline ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3 h-3 text-neutral-900 dark:text-neutral-200 inline ml-1" />
    ) : (
      <ArrowDown className="w-3 h-3 text-neutral-900 dark:text-neutral-200 inline ml-1" />
    );
  };

  const providerOptions: ProviderFilter[] = ['All', 'OpenAI', 'Anthropic', 'Open-Source'];

  return (
    <div className="space-y-4 font-sans">
      {/* Table Controls Bar: Segmented Pills & Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          {/* View Mode Segmented Control */}
          <div className="flex items-center space-x-2">
            <span className="text-neutral-500 dark:text-neutral-400 font-medium">View Mode:</span>
            <div className="bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 p-1 rounded-lg inline-flex items-center space-x-1">
              <button
                onClick={() => {
                  setViewMode('calibrated');
                  setSortColumn('bt_score');
                  setSortDirection('desc');
                }}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                  viewMode === 'calibrated'
                    ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 shadow-sm font-semibold'
                    : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 bg-transparent'
                }`}
              >
                Calibrated (&theta;)
              </button>
              <button
                onClick={() => {
                  setViewMode('raw');
                  setSortColumn('raw_win_rate');
                  setSortDirection('desc');
                }}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                  viewMode === 'raw'
                    ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 shadow-sm font-semibold'
                    : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 bg-transparent'
                }`}
              >
                Raw Win Rate
              </button>
            </div>
          </div>

          {/* Model Provider Filter Pills */}
          <div className="flex items-center space-x-2">
            <span className="text-neutral-500 dark:text-neutral-400 font-medium">Provider:</span>
            <div className="bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 p-1 rounded-lg inline-flex items-center space-x-1">
              {providerOptions.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setProviderFilter(opt)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                    providerFilter === opt
                      ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 shadow-sm font-semibold'
                      : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 bg-transparent'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Action Controls: Export CSV, Recalculate, & Refresh */}
        <div className="flex items-center space-x-2 self-start lg:self-auto font-mono">
          <button
            onClick={handleExportCSV}
            disabled={!filteredData || filteredData.length === 0}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs disabled:opacity-40"
          >
            <Download className="w-3 h-3 text-neutral-500 dark:text-neutral-400" />
            <span>Export CSV</span>
          </button>

          {onRecalculate && (
            <button
              onClick={onRecalculate}
              disabled={loading}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs disabled:opacity-40"
              title="Run dynamic Bradley-Terry MLE & Length Neutralization calculations on database"
            >
              <RotateCcw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              <span>Recalculate MLE</span>
            </button>
          )}

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          )}
        </div>
      </div>

      {/* Error State */}
      {error ? (
        <div className="p-8 text-center text-xs text-neutral-600 dark:text-neutral-400 space-y-2 border-y border-neutral-200 dark:border-neutral-800">
          <p className="text-neutral-800 dark:text-neutral-300 font-medium">{error}</p>
          <p className="text-neutral-500 font-mono">Verify backend server is running on http://localhost:8000</p>
        </div>
      ) : loading ? (
        <div className="p-8 text-center text-xs font-mono text-neutral-500 border-y border-neutral-200 dark:border-neutral-800 space-y-2">
          <div className="flex items-center justify-center space-x-2">
            <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
            <span>Computing Bradley-Terry MLE & Length Neutralization scores from database...</span>
          </div>
        </div>
      ) : (
        /* Flat Borderless Table with Subtle Top/Bottom Row Borders & Micro-Interactions */
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-y border-neutral-200 dark:border-neutral-800 text-xs font-semibold text-neutral-500 uppercase tracking-wider select-none font-mono">
                <th className="py-3 px-4 text-left w-12">Rank</th>
                <th
                  onClick={() => handleSort('model')}
                  className="py-3 px-4 text-left cursor-pointer hover:text-neutral-900 dark:hover:text-neutral-200 transition-colors group"
                >
                  Model {renderSortIndicator('model')}
                </th>
                <th className="py-3 px-4 text-left">Provider</th>
                <th
                  onClick={() => handleSort('raw_win_rate')}
                  className="py-3 px-4 text-center cursor-pointer hover:text-neutral-900 dark:hover:text-neutral-200 transition-colors group"
                >
                  Raw Win Rate {renderSortIndicator('raw_win_rate')}
                </th>
                <th
                  onClick={() => handleSort('bt_score')}
                  className="py-3 px-4 text-center cursor-pointer hover:text-neutral-900 dark:hover:text-neutral-200 transition-colors group"
                >
                  BT Score (&theta;) {renderSortIndicator('bt_score')}
                </th>
                <th
                  onClick={() => handleSort('neutralized_score')}
                  className="py-3 px-4 text-center cursor-pointer hover:text-neutral-900 dark:hover:text-neutral-200 transition-colors group"
                >
                  Neutralized Score {renderSortIndicator('neutralized_score')}
                </th>
                <th className="py-3 px-4 text-center">Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/70 text-neutral-800 dark:text-neutral-300">
              {filteredData.length > 0 ? (
                filteredData.map((item, idx) => {
                  const provider = getProvider(item.model);
                  const winPct = (item.raw_win_rate * 100).toFixed(1);

                  return (
                    <tr
                      key={item.model}
                      className="hover:bg-neutral-100 dark:hover:bg-neutral-800/40 transition-colors duration-150"
                    >
                      <td className="py-3 px-4 text-left font-mono text-xs tabular-nums tracking-tight font-semibold text-neutral-700 dark:text-neutral-300">
                        #{idx + 1}
                      </td>
                      <td className="py-3 px-4 text-left font-sans text-xs">
                        <div className="flex items-center justify-start space-x-2 font-medium text-neutral-900 dark:text-neutral-100">
                          <ModelIcon modelName={item.model} className="w-4 h-4 shrink-0" />
                          <span>{formatModelName(item.model)}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-left text-neutral-600 dark:text-neutral-400 font-sans text-xs">
                        {provider}
                      </td>
                      <td
                        className={`py-3 px-4 text-center font-mono text-xs tabular-nums tracking-tight ${
                          viewMode === 'raw'
                            ? 'text-neutral-900 dark:text-neutral-100 font-bold'
                            : 'text-neutral-500 dark:text-neutral-400'
                        }`}
                      >
                        {winPct}%
                      </td>
                      <td
                        className={`py-3 px-4 text-center font-mono text-xs tabular-nums tracking-tight font-semibold ${
                          viewMode === 'calibrated'
                            ? 'text-neutral-900 dark:text-neutral-100 font-bold'
                            : 'text-neutral-500 dark:text-neutral-400'
                        }`}
                      >
                        {item.bt_score >= 0
                          ? `+${item.bt_score.toFixed(4)}`
                          : item.bt_score.toFixed(4)}
                      </td>
                      <td
                        className={`py-3 px-4 text-center font-mono text-xs tabular-nums tracking-tight ${
                          viewMode === 'calibrated'
                            ? 'text-neutral-700 dark:text-neutral-200 font-medium'
                            : 'text-neutral-400 dark:text-neutral-500'
                        }`}
                      >
                        {item.neutralized_score >= 0
                          ? `+${item.neutralized_score.toFixed(5)}`
                          : item.neutralized_score.toFixed(5)}
                      </td>
                      <td className="py-3 px-4 text-center font-sans text-xs">
                        {getTierBadge(item.quality_tier)}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-neutral-500 font-mono text-xs">
                    No leaderboard data found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
