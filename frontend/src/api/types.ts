export interface LeaderboardItem {
  model: string;
  raw_win_rate: number;
  bt_score: number;
  quality_tier: string;
  neutralized_score: number;
}

export interface VerbosityDataPoint {
  word_count_diff: number;
  llm_verdict: number; // 1.0 = A, 0.5 = Tie, 0.0 = B
}

export interface PositionData {
  position_a: number | null;
  position_b: number | null;
  tie: number | null;
}

export interface DomainKappaPoint {
  domain: string;
  kappa: number | null;
}

export interface FormatBiasData {
  markdown_chosen: number | null;
  plain_text_chosen: number | null;
  p_value: number | null;
  p_value_adjusted?: number | null;
  chi2_stat: number | null;
}

export interface BiasStatsResponse {
  evidence_class: 'LEGACY_EXPLORATORY';
  status: 'AVAILABLE' | 'NO_DATA';
  n: number;
  verbosity_data: VerbosityDataPoint[];
  position_data: PositionData;
  domain_kappa: DomainKappaPoint[];
  format_bias: FormatBiasData;
  inter_judge_kappa?: number;
}

export interface QualitativeRecord {
  prompt_id: number | string;
  reasoning_text: string;
  word_count_diff: number;
  human_winner: string;
  ai_winner: string;
  model_names: string;
  prompt_text?: string;
  answer_a_text?: string;
  answer_b_text?: string;
  answer_a_model?: string;
  answer_b_model?: string;
  answer_a_id?: number;
  answer_b_id?: number;
  provenance_status?: 'VERIFIED' | 'UNAVAILABLE';
}

export type QualitativeBucket = 'verbosity' | 'forced_choice' | 'position_bias' | 'baseline_alignment';

export interface EvaluateRequest {
  prompt: string;
  answer_a: string;
  answer_b: string;
  model_name?: string;
}

export interface EvaluateResponse {
  winner: string;
  verbatim_reasoning: string;
  model_name: string;
}

export interface CalibratedEvaluateRequest {
  question: string;
  answer_a: string;
  answer_b: string;
  model_name?: string;
  temperature?: number;
  mitigation_strategy?: 'dual_ab' | 'verbosity_penalized' | 'none';
}

export interface CalibratedEvaluateResponse {
  status: string;
  original_order_winner: string;
  swapped_order_winner: string;
  final_calibrated_winner: string;
  position_bias_detected: boolean;
  detailed_reasoning: string;
  total_input_tokens: number;
  total_output_tokens: number;
  model_name: string;
}

export interface EnsembleEvaluateRequest {
  question: string;
  answer_a: string;
  answer_b: string;
  judge_models: string[];
  temperature?: number;
  mitigation_strategy?: 'dual_ab' | 'verbosity_penalized' | 'none';
}

export interface EnsembleIndividualResult {
  model_name: string;
  status: 'success' | 'failed';
  verdict: string;
  position_bias_detected?: boolean;
  reasoning: string;
  input_tokens: number;
  output_tokens: number;
  error?: string;
}

export interface EnsembleEvaluateResponse {
  status: string;
  consensus_verdict: string;
  vote_counts: Record<string, number>;
  individual_results: EnsembleIndividualResult[];
  total_models: number;
  successful_models: number;
  total_input_tokens: number;
  total_output_tokens: number;
}


export interface InterJudgeReliability {
  evidence_class: 'LEGACY_EXPLORATORY';
  status: 'AVAILABLE' | 'NO_DATA';
  n: number;
  inter_judge_kappa: number | null;
  overlapping_trials: number;
  agreement_rate: number | null;
  model_a: string;
  model_b: string;
}

export interface ConsistencyStatsResponse {
  evidence_class: 'LEGACY_EXPLORATORY';
  status: 'AVAILABLE' | 'NO_DATA';
  n: number;
  judge_model: string;
  overall_consistency_score: number | null;
  position_consistency_rate: number | null;
  cross_category_consistency_rate: number | null;
  inconsistencies_count: number | null;
  inter_judge_reliability?: InterJudgeReliability;
}

export interface DatasetCountResponse {
  status: 'AVAILABLE' | 'NO_DATA' | 'UNAVAILABLE';
  count: number | null;
  message: string;
}

export interface SelfPreferenceResponse {
  evidence_class: 'LEGACY_EXPLORATORY';
  status: 'AVAILABLE' | 'NO_DATA';
  n: number;
  judge_model: string;
  judge_family: string;
  self_win_rate: number | null;
  baseline_win_rate: number | null;
  self_preference_ratio: number | null;
  self_preference_detected: boolean;
  total_self_matchups: number;
  total_other_matchups: number;
  p_value: number | null;
  statistically_significant: boolean;
}

export interface CategoryBreakdownItem {
  category: string;
  baseline_kappa: number;
  calibrated_kappa: number;
  delta_kappa: number;
}

export interface MacroBenchmarkResponse {
  judge_model: string;
  total_evaluations: number;
  baseline_kappa: number;
  calibrated_kappa: number;
  delta_kappa: number;
  baseline_accuracy: number;
  calibrated_accuracy: number;
  delta_accuracy: number;
  baseline_flip_rate: number;
  mitigated_flip_rate: number;
  flip_rate_reduction: number;
  baseline_length_bias?: number;
  mitigated_length_bias?: number;
  length_bias_reduction?: number;
  category_breakdown?: CategoryBreakdownItem[];
  message: string;
}

/**
 * Current authoritative controlled-results API contract. Values are deliberately
 * nullable: `NOT_ESTIMABLE` and absent controlled evidence must never render as 0.
 */
export type ControlledEvidenceClass = 'CONTROLLED' | 'DRY_RUN_MOCK';
export type ControlledMetricStatus = 'ESTIMABLE' | 'NOT_ESTIMABLE' | 'NO_DATA';

export interface ControlledMetricResult {
  rq: string;
  metric_key?: string;
  judge: string | null;
  condition: string | null;
  metric: string;
  value: number | null;
  numerator: number | null;
  denominator: number | null;
  eligible_n: number;
  analyzed_n: number;
  ties: number;
  unknowns: number;
  failures: number;
  excluded: number;
  ci_low: number | null;
  ci_high: number | null;
  status: ControlledMetricStatus | string;
  analysis_version: string;
  evidence_class: ControlledEvidenceClass;
}

export interface ControlledResultsAccounting {
  planned_units: number;
  succeeded_units: number;
  valid_partial_units: number;
  failed_units: number;
  pending_units: number;
  planned_pass_slots: number;
  valid_returned_passes: number;
  failed_pass_slots: number;
  provider_error_pass_slots?: number;
  invalid_response_pass_slots?: number;
  paired_excluded_valid_pass_slots?: number;
}

export interface ControlledResultsResponse {
  status: 'NO_CONTROLLED_EVIDENCE' | 'CONTROLLED_RESULTS_PENDING_ANALYSIS' | string;
  evidence_class: 'CONTROLLED';
  executed_runs: number;
  executed_passes: number;
  accounting: ControlledResultsAccounting | null;
  analysis_runs: Record<string, string>;
  results: ControlledMetricResult[];
  message: string;
}

export function isControlledResultsAccounting(value: unknown): value is ControlledResultsAccounting {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  return ['planned_units', 'succeeded_units', 'valid_partial_units', 'failed_units', 'pending_units', 'planned_pass_slots', 'valid_returned_passes', 'failed_pass_slots']
    .every((key) => typeof row[key] === 'number');
}

/** Runtime guard for an untrusted future API response; no defaulting to zero. */
export function isControlledMetricResult(value: unknown): value is ControlledMetricResult {
  if (typeof value !== 'object' || value === null) return false;
  const row = value as Record<string, unknown>;
  const required = ['rq', 'judge', 'condition', 'metric', 'value', 'numerator', 'denominator', 'eligible_n', 'analyzed_n', 'ties', 'unknowns', 'failures', 'excluded', 'ci_low', 'ci_high', 'status', 'analysis_version', 'evidence_class'];
  return required.every((key) => Object.hasOwn(row, key) && row[key] !== undefined)
    && (row.evidence_class === 'CONTROLLED' || row.evidence_class === 'DRY_RUN_MOCK');
}

/** Reject malformed responses rather than giving the UI placeholder scientific values. */
export function isControlledResultsResponse(value: unknown): value is ControlledResultsResponse {
  if (typeof value !== 'object' || value === null) return false;
  const row = value as Record<string, unknown>;
  return row.evidence_class === 'CONTROLLED'
    && typeof row.status === 'string'
    && typeof row.executed_runs === 'number'
    && typeof row.executed_passes === 'number'
    && Array.isArray(row.results)
    && row.results.every(isControlledMetricResult)
    && (row.accounting === null || isControlledResultsAccounting(row.accounting))
    && typeof row.analysis_runs === 'object' && row.analysis_runs !== null && !Array.isArray(row.analysis_runs);
}




