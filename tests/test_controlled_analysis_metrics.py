from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_analysis_metrics import (  # noqa: E402
    ANALYSIS_VERSION, ControlledEvidence, RQ1Unit, RQ2Repetition, RQ3Pair, RQ6Unit, RQ7Observation, RQ7Pair, VariantPair,
    analyze_rq1, analyze_rq2, analyze_rq3, analyze_rq4, analyze_rq5, analyze_rq6, analyze_rq7, analyze_rq7_matched,
)


def evidence(rq, unit="u", judge="g", condition="c"):
    return dict(evidence_class="CONTROLLED", unit_id=unit, rq_code=rq, judge_name=judge, condition=condition)


def test_rq1_perfect_disagreement_ties_failures_kappa_and_reproducible_ci():
    rows = [RQ1Unit(**evidence("RQ1", str(i)), human_label=h, judge_label=j, category="cat") for i, (h, j) in enumerate([("ANSWER_A", "ANSWER_A"), ("ANSWER_B", "ANSWER_B"), ("TIE", "TIE"), ("ANSWER_A", "ANSWER_B"), ("ANSWER_A", "TIMEOUT")])]
    a = analyze_rq1(rows, seed=7, iterations=100)
    b = analyze_rq1(rows, seed=7, iterations=100)
    assert a["exact_agreement"].numerator == 3 and a["exact_agreement"].denominator == 4
    assert a["exact_agreement"].tie_count == 1 and a["exact_agreement"].failure_count == 1
    assert a["cohens_kappa"].value is not None and a["exact_agreement"].ci_low == b["exact_agreement"].ci_low
    one_class = analyze_rq1([RQ1Unit(**evidence("RQ1"), human_label="ANSWER_A", judge_label="ANSWER_A", category="c")])
    assert one_class["cohens_kappa"].status == "NOT_ESTIMABLE"


def test_rq2_uses_exact_groups_temperatures_repetitions_and_group_bootstrap():
    rows = [RQ2Repetition(**evidence("RQ2", f"a{i}"), group_key="pair-a-t0", answer_a_id=1, answer_b_id=2, temperature=0, repetition_index=i, retry_count=9, verdict="ANSWER_A" if i < 4 else "ANSWER_B") for i in range(5)]
    rows += [RQ2Repetition(**evidence("RQ2", f"b{i}"), group_key="pair-b-t7", answer_a_id=3, answer_b_id=4, temperature=.7, repetition_index=i, retry_count=0, verdict="ANSWER_B") for i in range(5)]
    result = analyze_rq2(rows, seed=9, iterations=100)["consistency"]
    assert result.denominator == 2 and result.value == .9 and result.bootstrap_iterations == 100


def test_rq2_rejects_mixed_route_identity_as_one_exact_configuration():
    rows = [RQ2Repetition(**evidence("RQ2", f"x{i}"), group_key="wrongly-merged", answer_a_id=1, answer_b_id=2, temperature=0, repetition_index=i, retry_count=0, verdict="ANSWER_A", configured_upstream_provider="a" if i < 4 else "b", observed_upstream_provider="a" if i < 4 else "b", routing_fingerprint="route-a" if i < 4 else "route-b") for i in range(5)]
    result = analyze_rq2(rows, iterations=20)["consistency"]
    assert result.status == "INSUFFICIENT_ELIGIBLE_UNITS"


def test_rq2_strict_primary_excludes_groups_with_nonvalid_repetitions_but_keeps_conditional_sensitivity():
    rows = [RQ2Repetition(**evidence("RQ2", f"a{i}"), group_key="all-valid", answer_a_id=1, answer_b_id=2, temperature=0, repetition_index=i, retry_count=0, verdict="ANSWER_A") for i in range(5)]
    rows += [RQ2Repetition(**evidence("RQ2", f"b{i}"), group_key="one-failure", answer_a_id=3, answer_b_id=4, temperature=0, repetition_index=i, retry_count=0, verdict="ANSWER_A" if i < 4 else "API_ERROR") for i in range(5)]
    result = analyze_rq2(rows, iterations=50)
    assert result["consistency"].denominator == 1
    assert result["strict_complete_repetition_consistency"].denominator == 1
    assert result["conditional_returned_judgment_consistency"].denominator == 2


def test_rq3_paired_flip_tie_incomplete_and_slot_imbalance_are_separate():
    rows = [RQ3Pair(**evidence("RQ3", "stable"), pass_ab="ANSWER_A", pass_ba="ANSWER_A", slot_wins_a=1), RQ3Pair(**evidence("RQ3", "flip"), pass_ab="ANSWER_A", pass_ba="ANSWER_B", slot_wins_a=2), RQ3Pair(**evidence("RQ3", "tie"), pass_ab="TIE", pass_ba="ANSWER_A"), RQ3Pair(**evidence("RQ3", "missing"), pass_ab="ANSWER_A", pass_ba=None)]
    result = analyze_rq3(rows, seed=8, iterations=100)
    assert result["paired_decisive_flip_rate"].value == .5 and result["paired_decisive_flip_rate"].denominator == 2
    assert result["all_paired_disagreement_rate"].value == 2 / 3
    assert result["slot_win_imbalance"].value == 1.0 and result["incomplete_pairs"].numerator == 1


@pytest.mark.parametrize("analyzer,rq", [(analyze_rq4, "RQ4"), (analyze_rq5, "RQ5")])
def test_rq4_rq5_controlled_variants_keep_denominators_and_reject_invalid(analyzer, rq):
    rows = [VariantPair(**evidence(rq, "variant"), variant_valid=True, variant_outcome="VARIANT", order="AB_BA"), VariantPair(**evidence(rq, "original"), variant_valid=True, variant_outcome="ORIGINAL", order="AB_BA"), VariantPair(**evidence(rq, "tie"), variant_valid=True, variant_outcome="TIE", order="AB_BA"), VariantPair(**evidence(rq, "bad"), variant_valid=False, variant_outcome="VARIANT", order="AB_BA")]
    result = analyzer(rows, seed=1, iterations=100)
    assert result["variant_win_rate"].value == 1 / 3 and result["variant_win_rate"].denominator == 3
    assert result["excluded_pair_count"].numerator == 1


def test_rq6_balanced_self_family_metric_rejects_missing_and_unbalanced_slots():
    rows = [RQ6Unit(**evidence("RQ6", "a"), source_family_complete=True, outcome="SELF", self_slot="A"), RQ6Unit(**evidence("RQ6", "b"), source_family_complete=True, outcome="OTHER", self_slot="B"), RQ6Unit(**evidence("RQ6", "missing"), source_family_complete=False, outcome=None, self_slot=None)]
    result = analyze_rq6(rows, iterations=100)["self_family_preference"]
    assert result.value == .5 and result.denominator == 2
    bad = analyze_rq6([RQ6Unit(**evidence("RQ6", str(i)), source_family_complete=True, outcome="SELF", self_slot="A") for i in range(3)])["self_family_preference"]
    assert bad.status == "UNBALANCED_PRESENTATION"


def test_rq7_preserves_positive_negative_equal_no_data_baseline_zero_and_tradeoff():
    rows = [RQ7Pair(**evidence("RQ7", "p1"), base_pair_key="p1", baseline={"agreement": .6, "position": .5, "zero": 0.0}, mitigation={"agreement": .8, "position": .2, "zero": .1}), RQ7Pair(**evidence("RQ7", "p2"), base_pair_key="p2", baseline={"agreement": .6, "position": .5, "zero": 0.0}, mitigation={"agreement": .4, "position": .2, "zero": .1})]
    result = analyze_rq7(rows)
    assert result["agreement"].value == 0.0 and result["position"].value == -.3 and result["zero"].value == .1
    assert analyze_rq7([])["delta"].status == "NOT_ESTIMABLE"


def test_rq7_matched_comparison_uses_only_common_valid_returned_decisions():
    rows = [
        RQ7Observation(**evidence("RQ7", "one"), base_pair_key="one", human_label="ANSWER_A", baseline_label="ANSWER_A", dual_ab_label="ANSWER_A", dual_ba_label="ANSWER_A"),
        RQ7Observation(**evidence("RQ7", "two"), base_pair_key="two", human_label="ANSWER_A", baseline_label="ANSWER_B", dual_ab_label="ANSWER_A", dual_ba_label="ANSWER_A"),
        RQ7Observation(**evidence("RQ7", "excluded"), base_pair_key="excluded", human_label="ANSWER_A", baseline_label="ANSWER_A", dual_ab_label="ANSWER_A", dual_ba_label="ANSWER_B"),
    ]
    result = analyze_rq7_matched(rows, iterations=50)
    assert result["baseline_agreement"].denominator == 2
    assert result["dual_swap_agreement"].denominator == 2
    assert result["agreement_delta"].value == 0.5
    assert result["baseline_coverage"].denominator == 3 and result["dual_swap_coverage"].denominator == 3


def test_controlled_only_version_and_zero_denominator_safety():
    with pytest.raises(ValueError): analyze_rq1([RQ1Unit(evidence_class="LEGACY_EXPLORATORY", unit_id="legacy", rq_code="RQ1", judge_name="g", condition="c", human_label="ANSWER_A", judge_label="ANSWER_A", category="c")])
    empty = analyze_rq3([])["paired_decisive_flip_rate"]
    assert empty.status == "NO_DATA" and empty.value is None and empty.metric_version == ANALYSIS_VERSION
