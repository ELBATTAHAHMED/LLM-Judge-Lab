import type { ControlledMetricResult } from './types';

export const RQ_TITLES: Record<string, string> = {
  RQ1: 'Human Alignment',
  RQ2: 'Stochastic Consistency',
  RQ3: 'Position Sensitivity',
  RQ4: 'Controlled Redundant-Length Effect',
  RQ5: 'Controlled Presentation-Format Effect',
  RQ6: 'Counterbalanced Matched Source-Family Preference',
  RQ7: 'Mitigation Trade-off',
};

const JUDGE_LABELS: Record<string, string> = {
  'gpt-4o-mini': 'GPT-4o-mini',
  'anthropic/claude-3-haiku': 'Claude',
  'deepseek/deepseek-chat': 'DeepSeek',
  'meta-llama/llama-3.3-70b-instruct': 'Llama',
};

const METRIC_LABELS: Record<string, string> = {
  rq1_exact_agreement: 'Agreement with human preference reference labels',
  rq1_cohens_kappa: "Cohen's kappa",
  rq2_strict_complete_repetition_consistency: 'Strict complete-repetition consistency',
  rq2_conditional_returned_judgment_consistency: 'Conditional returned-judgment consistency',
  rq3_paired_decisive_flip_rate: 'Paired decisive flip rate',
  rq3_all_paired_disagreement_rate: 'All-paired disagreement',
  rq3_slot_win_imbalance: 'Slot-win imbalance',
  rq3_incomplete_pair_count: 'Incomplete pair count',
  rq4_controlled_variant_win_rate: 'Redundant-length variant win rate',
  rq4_original_win_rate: 'Original variant win rate',
  rq4_excluded_pair_count: 'Excluded paired units',
  rq4_deterministic_transform_rejection_count: 'Deterministic transform rejection',
  rq4_presentation_order_disagreement_count: 'Presentation-order disagreement',
  rq4_operational_failure_count: 'Operational failure',
  rq4_invalid_or_incomplete_pair_count: 'Invalid or incomplete pair',
  rq4_stable_decisive_pair_count: 'Stable decisive pairs',
  rq4_stable_tie_pair_count: 'Stable tie pairs',
  rq5_controlled_variant_win_rate: 'Format variant win rate',
  rq5_original_win_rate: 'Original-format win rate',
  rq5_excluded_pair_count: 'Excluded paired units',
  rq5_deterministic_transform_rejection_count: 'Deterministic transform rejection',
  rq5_presentation_order_disagreement_count: 'Presentation-order disagreement',
  rq5_operational_failure_count: 'Operational failure',
  rq5_invalid_or_incomplete_pair_count: 'Invalid or incomplete pair',
  rq5_stable_decisive_pair_count: 'Stable decisive pairs',
  rq5_stable_tie_pair_count: 'Stable tie pairs',
  rq6_matched_self_family_preference: 'Matched source-family preference',
  rq6_counterbalanced_stable_same_family_preference: 'Stable same-family preference',
  rq6_counterbalanced_stable_other_family_preference: 'Stable other-family preference',
  rq6_counterbalanced_order_sensitive_disagreement: 'Order-sensitive disagreement',
  rq6_counterbalanced_valid_stable_decisive_coverage: 'Stable-decisive coverage',
  rq6_counterbalanced_tie_or_abstention_rate: 'Tie / abstention rate',
  rq6_counterbalanced_human_reference_agreement: 'Human-reference agreement',
  rq6_counterbalanced_human_reference_agreement_difference: 'Human-reference agreement difference',
  rq6_counterbalanced_equal_weight_judge_macro_average: 'Equal-weight judge macro-average',
  rq7_baseline_tie_rate: 'Baseline tie rate',
  rq7_baseline_failure_rate: 'Baseline failure rate',
  rq7_baseline_coverage: 'Baseline coverage',
  rq7_baseline_decisive_coverage: 'Baseline decisive coverage',
  rq7_dual_swap_tie_rate: 'DUAL_SWAP tie rate',
  rq7_dual_swap_failure_rate: 'DUAL_SWAP failure rate',
  rq7_dual_swap_coverage: 'DUAL_SWAP coverage',
  rq7_dual_swap_decisive_coverage: 'DUAL_SWAP decisive coverage',
  rq7_dual_swap_dual_pass_disagreement: 'Dual-pass disagreement',
  rq7_dual_swap_dual_pass_stability: 'Dual-pass stability',
  rq7_matched_retained_baseline_agreement: 'Matched retained baseline agreement',
  rq7_matched_retained_dual_swap_agreement: 'Matched retained DUAL_SWAP agreement',
  rq7_matched_retained_agreement_delta: 'Matched retained-decision difference',
  rq7_agreement_delta: 'Matched retained-decision difference',
  rq7_cohens_kappa_delta: "Cohen's kappa delta",
  rq7_tie_rate_delta: 'Tie-rate delta',
  rq7_failure_rate_delta: 'Failure-rate delta',
  rq7_coverage_delta: 'Coverage delta',
  rq7_decisive_coverage_delta: 'Decisive-coverage delta',
};

export const metricLabel = (metric: ControlledMetricResult): string => METRIC_LABELS[metric.metric] ?? metric.metric;
export const judgeLabel = (judge: string | null): string => judge ? (JUDGE_LABELS[judge] ?? judge) : 'All judges';
export const isKappaMetric = (metric: ControlledMetricResult): boolean => metric.metric.includes('kappa');
export const isCountMetric = (metric: ControlledMetricResult): boolean => metric.metric.endsWith('_count');
export const isDeltaMetric = (metric: ControlledMetricResult): boolean => (metric.metric_key ?? metric.metric).endsWith('_delta');

export const formatMetricValue = (metric: ControlledMetricResult): string => {
  if (metric.value === null || metric.status === 'NOT_ESTIMABLE' || metric.status === 'NO_DATA' || metric.status === 'UNBALANCED_PRESENTATION') return 'NOT ESTIMABLE';
  if (isCountMetric(metric)) return metric.value.toLocaleString();
  if (isKappaMetric(metric)) return metric.value.toFixed(4);
  if (isDeltaMetric(metric)) return `${metric.value > 0 ? '+' : ''}${(metric.value * 100).toFixed(2)} pp`;
  return `${(metric.value * 100).toFixed(2)}%`;
};

export const formatMetricCi = (metric: ControlledMetricResult): string => {
  if (metric.ci_low === null || metric.ci_high === null) return 'CI not estimable';
  if (isKappaMetric(metric)) return `95% CI: ${metric.ci_low.toFixed(4)}–${metric.ci_high.toFixed(4)}`;
  return `95% CI: ${(metric.ci_low * 100).toFixed(2)}–${(metric.ci_high * 100).toFixed(2)}%`;
};

export const rqInterpretation = (rq: string): string | null => ({
  RQ1: 'Agreement is measured against human preference reference labels; it is not an accuracy claim.',
  RQ2: 'Primary: strict complete-repetition consistency; conditional returned-judgment consistency is reported as a sensitivity analysis. No final temperature comparison is estimable under the frozen single-temperature protocol.',
  RQ4: 'This is a controlled redundant-length result and is not a broad verbosity-bias claim.',
  RQ5: 'Metrics exclude all 226 SUPERSEDED_CONTROLLED pre-fix runs.',
  RQ6: 'Presentation order is counterbalanced. Overall stable same-family preference is approximately balanced, with strong judge-level heterogeneity; source/content-quality confounding remains.',
  RQ7: 'Agreement is compared only on matched retained decisions; DUAL_SWAP reduced valid coverage descriptively on all planned units. This is not a causal treatment-effect claim.',
}[rq] ?? null);
