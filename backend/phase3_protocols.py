"""Frozen, provider-free methodology contracts for RQ1--RQ7.

These definitions are the only Phase 3 planning source.  They deliberately do
not import provider SDKs, legacy results, or execution code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from model_registry import MODEL_REGISTRY


PROTOCOL_VERSION = "phase3-controlled-v1"
PROMPT_TEMPLATE_VERSION = "controlled-judge-pairwise-v1"
PLANNED_BASE_UNIT_LIMIT = 200
ALL_JUDGES = tuple(MODEL_REGISTRY)
RQ6_JUDGES = ("gpt-4o-mini", "anthropic/claude-3-haiku", "meta-llama/llama-3.3-70b-instruct")

SCIENTIFIC_TERMINOLOGY: Mapping[str, str] = {
    "Ground Truth": "Human Preference Reference Labels",
    "Human Accuracy": "Agreement with Human Preferences",
    "Position Flip Rate": "Paired decisive flip rate (same matched pair only)",
    "Slot-Win Imbalance": "Aggregate positional imbalance proxy",
    "Format Bias Confirmed": "Requires validated controlled RQ5 evidence",
    "Self-Bias Confirmed": "Not permitted without adequate controlled evidence",
    "Bias Eliminated": "Not permitted without supporting evidence",
}


@dataclass(frozen=True)
class RQProtocol:
    rq_code: str
    research_question: str
    hypothesis: str
    eligibility: str
    unit_definition: str
    conditions: tuple[str, ...]
    judges: tuple[str, ...]
    pass_count: int
    repetitions: int
    counterbalancing: str
    primary_metric: str
    secondary_metrics: tuple[str, ...]
    tie_handling: str
    failure_handling: str
    exclusions: tuple[str, ...]
    required_metadata: tuple[str, ...]
    interpretation_limit: str
    temperatures: tuple[float, ...] = (0.0,)

    @property
    def protocol_version(self) -> str:
        return PROTOCOL_VERSION

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["protocol_version"] = PROTOCOL_VERSION
        result["prompt_template_version"] = PROMPT_TEMPLATE_VERSION
        return result


COMMON_METADATA = ("dataset_snapshot", "prompt_id", "answer_a_id", "answer_b_id", "judge_name", "provider", "requested_model", "prompt_template_version", "temperature", "top_p", "seed_policy", "condition", "repetition_index", "presentation_order")

PROTOCOLS: dict[str, RQProtocol] = {
    "RQ1": RQProtocol("RQ1", "How well do LLM judges agree with human preference/reference labels?", "Agreement with Human Preference Reference Labels is estimable on eligible exact answer pairs.", "Exact human-preference pairs with A/B/TIE reference labels.", "One immutable dataset/prompt/original-answer-pair/judge/configuration record.", ("BASELINE_STANDARD",), ALL_JUDGES, 1, 1, "No treatment slot claim; preserve recorded A/B order.", "Three-class exact agreement and Cohen's kappa with Human Preference Reference Labels.", ("category and judge strata", "tie behavior", "failure/unknown coverage", "confidence intervals"), "Human and judge ties are valid labels.", "UNKNOWN/INVALID_RESPONSE/API_ERROR/TIMEOUT are reported and excluded only from the stated valid-label denominator.", ("missing reference", "missing pair identity", "invalid configuration"), COMMON_METADATA + ("human_reference_label",), "Agreement is not human accuracy or objective truth."),
    "RQ2": RQProtocol("RQ2", "Does the same judge make the same decision when the same evaluation is repeated?", "Repeated identical pair/configuration evaluations quantify decision consistency.", "Complete pair metadata; repetitions share one immutable repetition-group key.", "Exact dataset/prompt/pair/judge/provider/template/temperature/top-p/seed-policy/condition group, with explicit repetition index.", ("TEMP_0_0", "TEMP_0_7"), ALL_JUDGES, 1, 5, "Presentation remains AB within each repetition; temperature conditions are separate.", "Within-group consistency rate and disagreement rate.", ("verdict distribution", "tie/failure frequency", "judge and temperature strata", "confidence intervals"), "TIE is a valid repeated outcome.", "Retries increment retry_count, never repetition_index; failures remain operational outcomes.", ("missing pair identity", "duplicate repetition index", "mixed configuration group"), COMMON_METADATA + ("repetition_group_id", "retry_count"), "Only same-unit repetitions support stochastic-consistency claims.", (0.0, 0.7)),
    "RQ3": RQProtocol("RQ3", "Does swapping Answer A and Answer B change the mapped decision?", "Matched original/swap presentations quantify position sensitivity under tested conditions.", "Exact answer pairs with both A/B and B/A passes present.", "One pair/judge/configuration with two independently persisted presentation passes.", ("POSITION_SWAP",), ALL_JUDGES, 2, 1, "Every unit contains AB and BA passes; no aggregate-only proxy substitutes for pairing.", "Paired decisive flip rate.", ("all paired disagreement", "tie disagreement", "slot-win imbalance", "incomplete-pair and failure rate", "confidence intervals"), "Tie-in-one, tie-in-both, and decisive-vs-tie remain distinct states.", "Unknown/invalid/provider failures are counted and cannot become flips.", ("incomplete swap pair", "missing original identity"), COMMON_METADATA + ("presented_answer_a_id", "presented_answer_b_id", "mapped_winner_id"), "Paired disagreement indicates position sensitivity, not automatic causal position bias."),
    "RQ4": RQProtocol("RQ4", "Does redundant extra length influence a judge when factual content is unchanged?", "Exact duplicated-text verbosity controls can isolate redundant-length effects.", "Nonempty transformable answers with a deterministic valid verbosity variant.", "One original answer and its checksum-linked redundant duplicate, evaluated in both slots.", ("VERBOSITY_REDUNDANCY",), ALL_JUDGES, 2, 1, "Each logical unit evaluates original/verbose and verbose/original.", "Verbose-version win/change rate on valid paired controls.", ("order-stratified outcome", "ties", "failure/invalid count", "confidence intervals"), "Tie is valid and separately reported.", "Invalid variants and execution failures are excluded with explicit counts.", ("empty text", "failed deterministic variant validation"), COMMON_METADATA + ("source_answer_id", "variant_checksum", "base_pair_key", "validation_status"), "Only this controlled redundant-text design supports a verbosity-effect statement; natural length is exploratory."),
    "RQ5": RQProtocol("RQ5", "Does formatting influence judgment when semantic content is preserved?", "Formatting-only controls with normalized text equivalence can isolate presentation effects.", "Nonempty answers with a deterministic content-equivalent format variant.", "One plain answer and checksum-linked formatting-only variant evaluated in both slots.", ("FORMAT_ONLY",), ALL_JUDGES, 2, 1, "Each logical unit evaluates plain/formatted and formatted/plain.", "Formatted-version win/change rate on content-equivalent pairs.", ("order-stratified outcome", "ties", "failure/invalid count", "confidence intervals"), "Tie is valid and separately reported.", "Content-equivalence failure blocks the unit.", ("empty text", "failed format-equivalence validation"), COMMON_METADATA + ("source_answer_id", "variant_checksum", "base_pair_key", "validation_status"), "Only validated content-equivalent controls support a format-effect statement."),
    "RQ6": RQProtocol("RQ6", "Does a judge prefer answers from its own source family under matched comparison?", "Balanced self-family versus other-family comparisons estimate source-family preference under documented confounding limits.", "Pairs with reliable stored source-model/family metadata and exactly one answer matching the allocated judge family.", "One source-identified self-family/other-family pair/judge/configuration with deterministic balanced slot assignment.", ("SOURCE_FAMILY_MATCHED",), RQ6_JUDGES, 1, 1, "Self-family answer is assigned A/B by stable pair hash; allocation must be balanced overall.", "Matched self-family preference rate, stratified by presented slot.", ("human-reference strata", "length/category/source-family covariates", "coverage and failure rate", "confidence intervals"), "Ties are valid non-decisions, not self/other wins.", "Missing/unreliable source metadata is an exclusion, never inferred from text.", ("missing source metadata", "no self-family answer", "unbalanced allocation"), COMMON_METADATA + ("answer_a_source_model", "answer_b_source_model", "answer_a_source_family", "answer_b_source_family", "judge_family", "human_reference_label"), "This is controlled/matched source-family preference evidence, not an unconditional self-bias confirmation."),
    "RQ7": RQProtocol("RQ7", "Can dual-pass mitigation reduce position sensitivity while maintaining human-preference agreement?", "The same base pairs permit a transparent baseline versus dual-swap trade-off comparison.", "Exact human-reference pairs eligible for both frozen strategies.", "One base pair/judge/configuration represented under baseline and dual-swap strategy conditions.", ("BASELINE_STANDARD", "DUAL_SWAP"), ALL_JUDGES, 1, 1, "Baseline uses AB; dual-swap contains AB and BA. Comparison is matched by base-pair key.", "Matched differences in agreement with Human Preference Reference Labels and paired position disagreement.", ("Cohen's kappa", "consistency where repeated", "tie/failure/coverage", "confidence intervals"), "Ties are preserved in each strategy and metric denominator.", "No data is NOT ESTIMABLE; failures and trade-offs remain visible.", ("base pair absent from either condition", "inconsistent configuration"), COMMON_METADATA + ("base_pair_key", "strategy", "human_reference_label"), "Mitigation is not successful by default; negative, null, and trade-off outcomes must remain visible."),
}


def get_protocol(rq_code: str) -> RQProtocol:
    try:
        return PROTOCOLS[rq_code]
    except KeyError as exc:
        raise ValueError(f"Unknown Phase 3 protocol {rq_code!r}") from exc
