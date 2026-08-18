# Phase 2 evaluation-engine boundary

## Authoritative future controlled path

`ControlledExecutionService` → `EvaluationRequest` validation → `MODEL_REGISTRY`
→ injected `ProviderAdapter` → strict `ProviderJudgement` validation → original
answer mapping → `ControlledPersistence` → `runs` and `passes`.

The Phase 2 implementation deliberately contains no live provider adapter. A
future adapter must return `ProviderResponse`, including any provider-returned
effective model, model version, request ID, and OpenRouter upstream model.
Absent identity is persisted explicitly as `NOT_RETURNED`; it is never inferred.

## Legacy and sandbox map (not authoritative controlled evidence)

| Entry point | Evaluation function | Persistence | Evidence boundary |
| --- | --- | --- | --- |
| Frontend `/api/evaluate` | `judge_engine.call_judge` | `judge_decisions`, `category=live` | `LIVE_SANDBOX` |
| Frontend `/api/evaluate/calibrated` | `judge_engine.call_calibrated_judge` | `judge_decisions`, `category=live_calibrated` | `LIVE_SANDBOX` |
| Frontend `/api/evaluate/ensemble` | `judge_engine.call_multi_judge_ensemble` | `judge_decisions`, `category=ensemble_eval` | `LIVE_SANDBOX` |
| `run_evaluation.py` | `judge_engine.call_judge` | `judge_decisions` | legacy exploratory |
| `run_batch_calibration.py` | `judge_engine.call_calibrated_judge` | `judge_decisions` | legacy exploratory |

Those compatibility paths are not invoked by the controlled engine. The local
Ollama routing no longer silently replaces a requested model with `llama3`.
The legacy calibrated flow remains historical/live-sandbox compatibility code;
future controlled dual passes use two `passes` rows and a neutral derived
`DISAGREEMENT` rather than a position-bias conclusion.

## Outcome contract

`ANSWER_A`, `ANSWER_B`, `TIE`, and `UNKNOWN` are valid judgement outcomes.
`INVALID_RESPONSE`, `API_ERROR`, and `TIMEOUT` are operational failures stored
as `ERROR` with distinct parse/error status. They cannot become ties or votes.
Confidence is persisted only as self-reported judge confidence, not a calibrated
probability.
