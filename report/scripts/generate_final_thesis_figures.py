"""Generate the two evidence-backed figures used in the final thesis results chapter.

The script intentionally reads the frozen source-corrected full-population artifact
instead of duplicating scientific values in plotting code.  It writes vector PDFs for
LaTeX and PNG previews for visual QA.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json"
OUTPUT = ROOT / "report/figures"

NAVY = "#25445D"
BLUE = "#507C99"
TEAL = "#527D78"
RUST = "#A5674B"
GRID = "#D7DEE5"
TEXT = "#20313D"
MUTED = "#5E6D78"
PANEL = "#F7F9FA"


def metric(results: dict[str, object], rq: str, key: str) -> dict[str, object]:
    return results[rq][key]  # type: ignore[index, no-any-return]


def percent(value: float) -> float:
    return value * 100


def save(fig: plt.Figure, stem: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(OUTPUT / f"{stem}.{suffix}", dpi=240 if suffix == "png" else None, bbox_inches="tight")
    plt.close(fig)


def load_results() -> dict[str, object]:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    return artifact["results"]


def generate_human_alignment_and_stability(results: dict[str, object]) -> None:
    agreement = metric(results, "RQ1", "exact_agreement")
    kappa = metric(results, "RQ1", "cohens_kappa")
    repeatability = metric(results, "RQ2", "strict_complete_repetition_consistency")
    flips = metric(results, "RQ3", "paired_decisive_flip_rate")

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.2), gridspec_kw={"wspace": 0.42})
    fig.patch.set_facecolor("white")

    ax = axes[0]
    ax.set_facecolor(PANEL)
    agreement_value = percent(float(agreement["value"]))
    ax.barh(["Agreement with\nhuman reference"], [agreement_value], color=NAVY, height=0.43)
    ax.text(agreement_value + 1.8, 0, f"{agreement_value:.2f}%", va="center", color=TEXT, fontsize=10, fontweight="bold")
    ax.text(
        0,
        -0.48,
        f"Cohen's $\\kappa$ = {float(kappa['value']):.4f}",
        color=MUTED,
        fontsize=9,
        va="center",
    )
    ax.set_title("Human alignment (RQ1)", color=TEXT, fontsize=10, fontweight="bold", loc="left", pad=10)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.set_ylim(-0.68, 0.62)

    ax = axes[1]
    ax.set_facecolor(PANEL)
    labels = ["Fixed-condition\nrepeatability", "Decisive\norder flips"]
    values = [percent(float(repeatability["value"])), percent(float(flips["value"]))]
    bars = ax.barh(labels, values, color=[TEAL, RUST], height=0.43)
    for bar, value in zip(bars, values, strict=True):
        ax.text(value + 1.8, bar.get_y() + bar.get_height() / 2, f"{value:.2f}%", va="center", color=TEXT, fontsize=10, fontweight="bold")
    ax.invert_yaxis()
    ax.set_title("Stability (RQ2 and RQ3)", color=TEXT, fontsize=10, fontweight="bold", loc="left", pad=10)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))

    for ax in axes:
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", labelsize=8.5, colors=TEXT, length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.text(
        0.5,
        0.02,
        "High fixed-condition repeatability and agreement with human preference reference labels are distinct properties.",
        ha="center",
        color=MUTED,
        fontsize=8.5,
    )
    fig.subplots_adjust(bottom=0.22, top=0.83, left=0.08, right=0.96)
    save(fig, "human-alignment-stability")


def generate_dual_swap_tradeoff(results: dict[str, object]) -> None:
    baseline_agreement = metric(results, "RQ7_PRIMARY", "baseline_agreement")
    dual_agreement = metric(results, "RQ7_PRIMARY", "dual_swap_agreement")
    agreement_delta = metric(results, "RQ7_PRIMARY", "agreement_delta")
    baseline_coverage = metric(results, "RQ7_PRIMARY", "baseline_coverage")
    dual_coverage = metric(results, "RQ7_PRIMARY", "dual_swap_coverage")
    coverage_delta = metric(results, "RQ7_PRIMARY", "coverage_delta")

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.45), gridspec_kw={"wspace": 0.42})
    fig.patch.set_facecolor("white")
    labels = ["Baseline", "DUAL_SWAP"]

    panels = [
        (
            axes[0],
            "Agreement on matched retained decisions",
            [percent(float(baseline_agreement["value"])), percent(float(dual_agreement["value"]))],
            f"Change: {percent(float(agreement_delta['value'])):+.2f} pp\n95% CI {percent(float(agreement_delta['ci_low'])):+.2f} to {percent(float(agreement_delta['ci_high'])):+.2f} pp",
            "Matched retained subset: n = 597",
        ),
        (
            axes[1],
            "Coverage across linked triplets",
            [percent(float(baseline_coverage["value"])), percent(float(dual_coverage["value"]))],
            f"Change: {percent(float(coverage_delta['value'])):+.2f} pp",
            "Eligible linked triplets: n = 799",
        ),
    ]

    for ax, title, values, annotation, denominator in panels:
        ax.set_facecolor(PANEL)
        bars = ax.bar(labels, values, color=[BLUE, TEAL], width=0.56)
        for bar, value in zip(bars, values, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 2.0, f"{value:.2f}%", ha="center", va="bottom", color=TEXT, fontsize=9.5, fontweight="bold")
        ax.text(0.5, 0.95, annotation, transform=ax.transAxes, ha="center", va="top", color=TEXT, fontsize=8.5, linespacing=1.35)
        ax.text(0.5, -0.18, denominator, transform=ax.transAxes, ha="center", va="top", color=MUTED, fontsize=8)
        ax.set_title(title, color=TEXT, fontsize=10, fontweight="bold", loc="left", pad=10)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", labelsize=8.5, colors=TEXT, length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.text(
        0.5,
        0.02,
        "The agreement interval includes zero; DUAL_SWAP is therefore presented as a trade-off, not a significant improvement claim.",
        ha="center",
        color=MUTED,
        fontsize=8.3,
    )
    fig.subplots_adjust(bottom=0.27, top=0.83, left=0.08, right=0.96)
    save(fig, "dual-swap-agreement-coverage-tradeoff")


def main() -> None:
    results = load_results()
    generate_human_alignment_and_stability(results)
    generate_dual_swap_tradeoff(results)


if __name__ == "__main__":
    main()
