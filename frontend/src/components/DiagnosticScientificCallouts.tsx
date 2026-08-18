import React from 'react';

export const DiagnosticScientificCallouts: React.FC = () => {
  return (
    <div className="space-y-4 font-sans">
      {/* Main Thesis Executive Synthesis Panel */}
      <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-2 transition-colors duration-150">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs tracking-tight">
            Academic Research Takeaway &amp; Synthesis
          </h4>
          <span className="text-[11px] font-mono text-neutral-500">
            Master PFE Thesis Chapter 4 &amp; 5 Summary
          </span>
        </div>

        <blockquote className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed border-l-2 border-neutral-400 dark:border-neutral-600 pl-3 py-1 font-mono">
          "Historical exploratory telemetry suggests associations with presentation position and answer length. Frozen controlled experiments are required before making causal RQ claims."
        </blockquote>
      </div>

      {/* 3 Detailed Scientific Callout Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
        {/* Callout 1: Position Distortion */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
          <div className="space-y-2 flex-1 mb-3">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
              <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs">Position-Order Distortion</h5>
              <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">
                Binary &chi;&sup2; Test
              </span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              The Chi-Square test evaluates position selection against a 50/50 uniform baseline. Reversing presentation order exposes systematic position preference for candidate responses.
            </p>
          </div>
          <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 text-[11px] font-mono text-neutral-500">
            Mitigation: Dual A/B Order Randomization
          </div>
        </div>

        {/* Callout 2: Verbosity Inflation */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
          <div className="space-y-2 flex-1 mb-3">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
              <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs">Verbosity &amp; Vocabulary Shift</h5>
              <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">
                Spearman &rho; Correlation
              </span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              Spearman rank correlation measures length bias. Reasoning texts exhibit vocabulary shifts toward length-justifying bi-grams (<em>"provides more"</em>, <em>"more comprehensive"</em>).
            </p>
          </div>
          <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 text-[11px] font-mono text-neutral-500">
            Mitigation: Residual Length Neutralization
          </div>
        </div>

        {/* Callout 3: Decisiveness Hallucinations */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
          <div className="space-y-2 flex-1 mb-3">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
              <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs">Forced Choice &amp; Hedging</h5>
              <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">
                Forced Choice Delta
              </span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              On human-rated ties, the LLM judge often forces a winner while increasing hedging vocabulary using words like <em>"slightly"</em>, <em>"marginal"</em>, and <em>"subtle"</em>.
            </p>
          </div>
          <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 text-[11px] font-mono text-neutral-500">
            Mitigation: Rubric tie thresholding
          </div>
        </div>
      </div>
    </div>
  );
};

