# Phase 3 controlled methodology contract

Canonical protocol definitions live in `backend/phase3_protocols.py` at
`phase3-controlled-v1`. Planning is provider-free and execution is deliberately
disabled by `phase3_planning.execution_is_disabled`.

| RQ | Frozen controlled design | Primary metric | Interpretation limit |
| --- | --- | --- | --- |
| RQ1 | Exact human-reference pair × judge | Three-class agreement and Cohen's kappa | Agreement with Human Preference Reference Labels, never human accuracy. |
| RQ2 | Exact pair/configuration repeated five times at 0.0 and 0.7 | Within-group consistency | Only identical repeated units support stochastic claims. |
| RQ3 | Same pair under AB and BA | Paired decisive flip rate | Position sensitivity, not automatic causal bias. |
| RQ4 | Original versus exact duplicated-text control in both slots | Verbose-control win/change rate | Natural length associations remain exploratory. |
| RQ5 | Plain versus syntax-only equivalent format control in both slots | Formatted-control win/change rate | Only validated equivalent variants support a format-effect claim. |
| RQ6 | Stored source-family self/other pair with alternating self slot | Matched self-family preference rate | Controlled/matched association, not unconditional self-bias confirmation. |
| RQ7 | Same base unit under standard single-pass and dual-swap | Matched agreement/position-sensitivity changes | Negative, null, and trade-off results are preserved; no data is not estimable. |

## Non-provider validation gates

- RQ1: valid A/B/TIE human reference and distinct answer pair.
- RQ2: full pair/configuration identity, unique repetition indexes, retries
  separate from repetitions, and temperature strata separate.
- RQ3: both matched presentation passes required; slot-win imbalance is not a
  paired flip metric.
- RQ4: the only accepted verbosity variant is `original + blank line + original`.
  Any addition or alteration is rejected.
- RQ5: normalized original text must exactly equal formatting-syntax-stripped
  variant text. No headings or semantic labels are generated.
- RQ6: source family comes only from stored source-model metadata mapping; it
  is never inferred from answer text. DeepSeek is excluded because this dataset
  contains no DeepSeek answer-source family.
- RQ7: each base-pair/judge must have both frozen strategies.

The terminology contract is centralized in `SCIENTIFIC_TERMINOLOGY`; frontend
changes remain a later phase.
