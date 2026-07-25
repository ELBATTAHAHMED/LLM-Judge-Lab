export interface LeaderboardItem {
  model: string;
  raw_win_rate: number;
  bt_score: number;
  quality_tier: string;
  neutralized_score: number;
  rank_change: number;
}

export interface VerbosityDataPoint {
  word_count_diff: number;
  llm_verdict: number; // 1.0 = A, 0.5 = Tie, 0.0 = B
}

export interface PositionData {
  position_a: number;
  position_b: number;
  tie: number;
}

export interface DomainKappaPoint {
  domain: string;
  kappa: number;
}

export interface FormatBiasData {
  markdown_chosen: number;
  plain_text_chosen: number;
  p_value: number;
  p_value_adjusted?: number;
  chi2_stat: number;
}

export interface BiasStatsResponse {
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

export interface ResultSummary {
  total_evaluated: number;
  winner_a_count: number;
  winner_b_count: number;
  tie_count: number;
  position_bias_flips: number;
  overall_accuracy_vs_human: number;
  mitigation_strategy: string;
}

export interface ExperimentJobStatus {
  job_id: string;
  job_type?: 'batch' | 'perturbations' | 'stochastic';
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  total: number;
  percentage: number;
  message: string;
  logs: string[];
  result_summary?: ResultSummary;
}

export interface BatchRunRequest {
  sample_size?: number;
  model_name?: string;
  temperature?: number;
  mitigation_strategy?: 'dual_ab' | 'verbosity_penalized' | 'none';
}

export interface PerturbationRunRequest {
  padding_factor?: number;
  inject_markdown?: boolean;
}

export interface StochasticRunRequest {
  n_trials?: number;
  model_name?: string;
}
