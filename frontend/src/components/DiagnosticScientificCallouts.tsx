import React from 'react';

export const DiagnosticScientificCallouts: React.FC = () => {
  return (
    <div className="space-y-4 font-sans">
      <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-2 transition-colors duration-150">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs tracking-tight">
            Historical Exploratory Telemetry
          </h4>
          <span className="text-[11px] font-mono text-neutral-500">Not final controlled evidence</span>
        </div>
        <p className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed border-l-2 border-neutral-400 dark:border-neutral-600 pl-3 py-1 font-mono">
          These retained telemetry views describe historical associations only. They are not part of the final controlled RQ1–RQ7 evidence and do not establish causal effects.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
          <div className="space-y-2 flex-1 mb-3">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
              <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs">Exploratory Position-Order Telemetry</h5>
              <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">Binary &chi;&sup2; Test</span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              Historical slot-selection counts are compared with a 50/50 reference as an exploratory descriptive check. This view does not establish a general position effect.
            </p>
          </div>
          <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 text-[11px] font-mono text-neutral-500">Historical association only</div>
        </div>

        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
          <div className="space-y-2 flex-1 mb-3">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
              <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs">Answer-Length Association</h5>
              <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">Spearman &rho; Correlation</span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              This exploratory correlation summarizes historical answer-length and selection patterns. It is not a controlled estimate of a redundant-length effect.
            </p>
          </div>
          <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 text-[11px] font-mono text-neutral-500">Exploratory heuristic</div>
        </div>

        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
          <div className="space-y-2 flex-1 mb-3">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
              <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs">Historical Decisiveness Telemetry</h5>
              <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">Forced Choice Delta</span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              Historical decisions near human-reference ties are displayed for exploration. They do not validate a final rubric or mitigation method.
            </p>
          </div>
          <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 text-[11px] font-mono text-neutral-500">Not part of final controlled evidence</div>
        </div>
      </div>
    </div>
  );
};
