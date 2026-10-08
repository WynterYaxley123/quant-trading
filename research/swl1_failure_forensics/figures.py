"""Deterministic static figures from public aggregates, never private panels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .report import public_safe

PHASES = ("v1_development", "v1_validation", "v2_development", "v2_validation")
LABELS = ("V1 Dev", "V1 Val", "V2 Dev", "V2 Val")
COLORS = ("#31688e", "#35b779", "#e58a30")


def generate(summary: dict[str, Any], output: Path) -> list[str]:
    public_safe(summary)
    if summary["replay_parity"] != "PASS":
        raise ValueError("REPLAY_PARITY_REQUIRED_FOR_FIGURES")
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"svg.hashsalt": "SWL1-FORENSICS", "svg.fonttype": "none", "font.size": 10})
    produced: list[str] = []

    def save(fig: Any, name: str, definition: str) -> None:
        fig.text(
            0.02,
            0.015,
            "EXPLORATORY_POST_HOC | source: summary.json; consumed frozen fits only\n"
            + definition
            + " | overlapping labels; no causal or independent validation claim",
            fontsize=8,
        )
        fig.tight_layout(rect=(0, 0.08, 1, 0.95))
        fig.savefig(output / (name + ".svg"), metadata={"Date": None, "Description": definition})
        target = output / (name + ".svg")
        target.write_text(
            "\n".join(line.rstrip() for line in target.read_text().splitlines()) + "\n"
        )
        plt.close(fig)
        produced.append(name + ".svg")

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(4)
    for index, horizon in enumerate((10, 40, 120)):
        ax.bar(
            x + (index - 1) * 0.23,
            [
                summary["phases"][p]["original_metrics"]["horizons"][str(horizon)]["mean_rank_ic"]
                for p in PHASES
            ],
            width=0.23,
            color=COLORS[index],
            label=f"H{horizon}",
        )
    ax.set_xticks(x, LABELS)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_ylabel("Mean Spearman RankIC")
    ax.legend()
    ax.set_title("Frozen selected fits: horizon outcomes")
    save(fig, "horizon-outcomes", "Mean daily RankIC over each native Dev/Val signal range")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, phase, label in zip(axes.flat, PHASES, LABELS, strict=True):
        blocks = summary["phases"][phase]["unified_calendar_blocks"]
        for index, horizon in enumerate((10, 40, 120)):
            ax.plot(
                [b["block"] for b in blocks],
                [b["horizon_rank_ic"][str(horizon)] for b in blocks],
                marker="o",
                color=COLORS[index],
                label=f"H{horizon}",
            )
        ax.axhline(0, color="black", linewidth=0.7)
        ax.set_xticks([1, 2, 3, 4])
        ax.set_title(label)
        ax.set_ylabel("Block mean RankIC")
        ax.legend(fontsize=8)
    save(
        fig,
        "calendar-blocks",
        "Four equal-duration calendar blocks per phase; bounds/counts in summary",
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for index, horizon in enumerate((10, 40, 120)):
        for ax, key in zip(axes, ("effective_df_slope", "condition_regularized"), strict=True):
            ax.plot(
                x,
                [
                    summary["phases"][p]["horizons"][str(horizon)]["numerical"][key]["median"]
                    for p in PHASES
                ],
                marker="o",
                color=COLORS[index],
                label=f"H{horizon}",
            )
            ax.set_xticks(x, LABELS)
            ax.set_title(key)
            ax.legend()
    axes[1].set_yscale("log")
    save(
        fig,
        "ridge-conditioning",
        "Per-fit medians; df=sum eigen/(eigen+alpha), regularized Gram condition",
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    names = summary["phases"]["v2_validation"]["factor_names"]
    for ax, phase, label in zip(
        axes, ("v1_validation", "v2_validation"), ("V1 Val", "V2 Val"), strict=True
    ):
        matrix = np.asarray(summary["phases"][phase]["factor_correlation"], dtype=float)
        plot = ax.imshow(matrix, vmin=-1, vmax=1, cmap="RdBu_r")
        ax.set_xticks(range(19), names, rotation=90)
        ax.set_yticks(range(19), names)
        ax.set_title(label)
        fig.colorbar(plot, ax=ax, fraction=0.046, pad=0.04)
    save(
        fig,
        "factor-correlations",
        "Pooled Pearson correlations of 19 frozen factors across phase signals x 30 industries",
    )

    fig, axes = plt.subplots(1, 2, figsize=(11, 7))
    for ax, phase, label in zip(
        axes, ("v1_validation", "v2_validation"), ("V1 Val", "V2 Val"), strict=True
    ):
        matrix = np.column_stack(
            [
                summary["phases"][phase]["horizons"][h]["coefficient_positive_fraction"]
                for h in ("10", "40", "120")
            ]
        )
        plot = ax.imshow(matrix, vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(3), ["H10", "H40", "H120"])
        ax.set_yticks(range(19), names)
        ax.set_title(label + ": coefficient positive fraction")
        fig.colorbar(plot, ax=ax, fraction=0.046, pad=0.04)
    save(
        fig,
        "coefficient-signs",
        "Fraction of selected standardized coefficients above zero; correlated factors are not independent effects",
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    pairs = ("10_40", "10_120", "40_120")
    for ax, phase, label in zip(
        axes, ("v1_validation", "v2_validation"), ("V1 Val", "V2 Val"), strict=True
    ):
        for index, key in enumerate(
            ("prediction_rank_correlation", "realized_rank_correlation", "top5_overlap_fraction")
        ):
            ax.bar(
                np.arange(3) + (index - 1) * 0.23,
                [summary["phases"][phase]["horizon_pairs"][p][key]["mean"] for p in pairs],
                width=0.23,
                label=key,
                color=COLORS[index],
            )
        ax.set_xticks(range(3), [p.replace("_", "/") for p in pairs])
        ax.set_title(label)
        ax.axhline(0, color="black", linewidth=0.7)
        ax.legend(fontsize=7)
    save(
        fig,
        "horizon-coherence",
        "Mean daily cross-horizon Spearman correlations and Top5 intersection/5",
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(
        x,
        [summary["phases"][p]["regime"]["industry_covariance_effective_dimension"] for p in PHASES],
        color="#31688e",
    )
    axes[1].bar(
        x,
        [summary["phases"][p]["regime"]["industry_covariance_first_pc_share"] for p in PHASES],
        color="#35b779",
    )
    for ax, title in zip(
        axes,
        ("Covariance effective dimension", "First principal component variance share"),
        strict=True,
    ):
        ax.set_xticks(x, LABELS)
        ax.set_title(title)
    save(
        fig,
        "cross-section",
        "Daily industry return covariance: trace(C)^2/trace(C^2); largest eigen/trace(C); not rank df",
    )
    return produced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(json.loads(args.summary.read_text()), args.output)))


if __name__ == "__main__":
    main()
