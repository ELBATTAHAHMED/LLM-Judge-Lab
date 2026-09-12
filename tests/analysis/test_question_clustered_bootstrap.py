from __future__ import annotations

from backend.analysis.question_clustered_bootstrap import question_clustered_bootstrap


def test_question_clusters_preserve_every_member_and_are_not_observation_resampled():
    rows = [
        {"question": 81, "value": "81-turn1-judgeA"},
        {"question": 81, "value": "81-turn2-judgeB"},
        {"question": 82, "value": "82-turn1-judgeA"},
    ]
    seen: list[list[dict[str, object]]] = []

    def statistic(sample):
        seen.append(list(sample))
        return 1.0

    result = question_clustered_bootstrap(
        rows,
        question_id=lambda row: row["question"],
        statistic=statistic,
        seed=7,
        resamples=20,
    )

    assert result.question_clusters == 2
    assert result.valid_replicates == 20
    for sample in seen:
        first_count = sum(row["question"] == 81 for row in sample)
        second_count = sum(row["question"] == 82 for row in sample)
        # A sampled question contributes its complete two-row or one-row block.
        assert first_count % 2 == 0
        assert first_count // 2 + second_count == 2


def test_question_clustered_bootstrap_is_deterministic_for_fixed_seed():
    rows = [
        {"question": 81, "value": 0.0},
        {"question": 81, "value": 1.0},
        {"question": 82, "value": 1.0},
        {"question": 83, "value": 1.0},
    ]
    kwargs = {
        "observations": rows,
        "question_id": lambda row: row["question"],
        "statistic": lambda sample: sum(row["value"] for row in sample) / len(sample),
        "seed": 20260912,
        "resamples": 500,
    }
    assert question_clustered_bootstrap(**kwargs) == question_clustered_bootstrap(**kwargs)


def test_non_estimable_replicates_are_counted_not_silently_dropped():
    rows = [{"question": 81, "value": 0}, {"question": 82, "value": 1}]

    result = question_clustered_bootstrap(
        rows,
        question_id=lambda row: row["question"],
        statistic=lambda sample: None if all(row["question"] == 81 for row in sample) else 1.0,
        seed=3,
        resamples=200,
    )

    assert 0 < result.non_estimable_replicates < 200
    assert result.valid_replicates + result.non_estimable_replicates == 200
    assert result.ci_low == result.ci_high == 1.0


def test_cluster_count_is_question_count_not_observation_count():
    rows = [{"question": 81, "value": value} for value in range(10)] + [{"question": 82, "value": 10}]
    result = question_clustered_bootstrap(
        rows,
        question_id=lambda row: row["question"],
        statistic=lambda sample: float(len(sample)),
        seed=11,
        resamples=50,
    )
    assert result.question_clusters == 2
    assert result.bootstrap_replicates == 50
