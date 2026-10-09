"""Six reproducible aggregate-only figures, never daily market payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .design import LABEL

CHARTS = (
    "signal-rankic.svg",
    "temporal-blocks.svg",
    "ridge-comparison.svg",
    "factor-target-correlations.svg",
    "industry-sensitivity.svg",
    "concentration-turnover.svg",
)


def render(public: Path, preview: Path | None = None) -> None:
    summary = json.loads((public / "research-summary.json").read_text())
    comparison = json.loads((public / "model-comparison.json").read_text())
    models = summary["models"]
    matplotlib.rcParams.update(
        {"font.size": 10, "svg.fonttype": "none", "svg.hashsalt": "SWL1_H5_H10_EXPLORATORY"}
    )

    def save(fig: Any, name: str, note: str) -> None:
        fig.suptitle("EXPLORATORY_POST_HOC | " + fig._suptitle.get_text(), fontsize=14)
        fig.text(
            0.5,
            0.01,
            "Signals 2023-08-02 to 2026-09-21 (H5) / 09-14 (H10); outcomes through 2026-09-29.\n30 reconstructed industries; dependent/consumed labels, unresolved PIT/rights. "
            + note,
            ha="center",
            fontsize=8,
        )
        fig.tight_layout(rect=(0, 0.10, 1, 0.92))
        fig.savefig(
            public / name,
            metadata={
                "Date": None,
                "Description": LABEL + "; aggregate only; no independent validation",
            },
        )
        svg = public / name
        svg.write_text(
            "\n".join(line.rstrip() for line in svg.read_text().splitlines()).rstrip() + "\n",
            encoding="utf-8",
        )
        if preview is not None:
            preview.mkdir(parents=True, exist_ok=True)
            fig.savefig(preview / name.replace(".svg", ".png"), dpi=120)
        plt.close(fig)

    specs = ("S1", "S2", "S3", "S4")
    names = ("REV5", "REV10", "Equal REV", "2-factor Ridge")
    colors = ("#2563eb", "#d97706")
    x = np.arange(4)
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.suptitle("Signal RankIC: fixed direction and one fixed Ridge")
    for j, h in enumerate(("5", "10")):
        means = np.array([models[s][h]["rank_ic"]["mean"] for s in specs])
        intervals = [models[s][h]["dependence"]["descriptive_block_interval"] for s in specs]
        lower = np.array([i["lower_5pct"] for i in intervals])
        upper = np.array([i["upper_95pct"] for i in intervals])
        ax.bar(x + (j - 0.5) * 0.32, means, 0.32, color=colors[j], label=f"H{h}")
        ax.errorbar(
            x + (j - 0.5) * 0.32,
            means,
            yerr=[means - lower, upper - means],
            fmt="none",
            capsize=4,
            color="#334155",
        )
    ax.axhline(0, color="#64748b", lw=0.8)
    ax.set_xticks(x, names)
    ax.set_ylabel("Mean cross-sectional Spearman RankIC")
    ax.legend()
    save(
        fig,
        CHARTS[0],
        "Whiskers: descriptive 5/95% circular block ranges (20 sessions, 500 draws), not independent confidence.",
    )
    fig, ax = plt.subplots(figsize=(11, 7))
    fig.suptitle("All four fixed calendar blocks")
    rows = [(s, h) for s in specs for h in ("5", "10")] + [("S5", "10")]
    matrix = np.array(
        [[b["rank_ic"]["mean"] for b in models[s][h]["calendar_blocks"]] for s, h in rows]
    )
    image = ax.pcolormesh(
        np.arange(5) - 0.5,
        np.arange(len(rows) + 1) - 0.5,
        matrix,
        cmap="RdBu",
        vmin=-0.13,
        vmax=0.13,
    )
    ax.invert_yaxis()
    ax.set_xticks(range(4), ["Block 1", "Block 2", "Block 3", "Block 4"])
    ax.set_yticks(range(len(rows)), [f"{s} H{h}" for s, h in rows])
    for i in range(len(rows)):
        for j in range(4):
            ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center")
    bar = fig.colorbar(image, ax=ax, label="Mean RankIC")
    if bar.solids is not None:
        bar.solids.set_rasterized(False)
    save(
        fig,
        CHARTS[1],
        "Equal calendar duration, assigned before filtering; S5 uses its 527 recorded H10 dates only.",
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle("Ridge minus simple signals on identical dates")
    for j, h in enumerate(("5", "10")):
        values = comparison["ridge_minus_simple"][h]
        axes[j].bar(
            range(3), [values[s]["delta_rank_ic"]["mean"] for s in specs[:3]], color=colors[j]
        )
        axes[j].axhline(0, color="#64748b", lw=0.8)
        axes[j].set_xticks(range(3), names[:3])
        axes[j].set_title(f"H{h}: " + str(values["S1"]["matched_signal_count"]) + " paired dates")
        axes[j].set_ylabel("Mean paired RankIC difference")
    save(
        fig,
        CHARTS[2],
        "EXPLORATORY_INFORMED_COMPARISON; negative means the extra fitting step reduced RankIC.",
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle("Reversal and future-target correlation structure")
    correlation = comparison["factor_target_correlations"]
    for j, field in enumerate(("pooled_pearson", "mean_daily_cross_sectional_pearson")):
        m = np.array(correlation[field])
        image = axes[j].pcolormesh(
            np.arange(5) - 0.5, np.arange(5) - 0.5, m, cmap="RdBu", vmin=-1, vmax=1
        )
        axes[j].invert_yaxis()
        axes[j].set_aspect("equal")
        axes[j].set_xticks(range(4), ["REV5", "REV10", "Y5", "Y10"])
        axes[j].set_yticks(range(4), ["REV5", "REV10", "Y5", "Y10"])
        axes[j].set_title(
            "Pooled relative observations" if j == 0 else "Mean daily cross-sectional Pearson"
        )
        for a in range(4):
            for b in range(4):
                axes[j].text(
                    b,
                    a,
                    f"{m[a, b]:.3f}",
                    ha="center",
                    va="center",
                    color="white" if abs(m[a, b]) > 0.6 else "black",
                )
    bar = fig.colorbar(image, ax=axes[1], fraction=0.046, pad=0.04)
    if bar.solids is not None:
        bar.solids.set_rasterized(False)
    save(
        fig,
        CHARTS[3],
        "757 common dates; correlated factors and overlapping horizons do not create independent samples.",
    )
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle("All 30 leave-one-industry-out diagnostics")
    for j, h in enumerate(("5", "10")):
        for s in ("S1", "S2", "S4"):
            values = models[s][h]["leave_one_industry_out"]
            axes[j].plot(range(30), [v["rank_ic"]["mean"] for v in values], marker=".", label=s)
        axes[j].axhline(0, color="#64748b", lw=0.8)
        axes[j].set_ylabel(f"H{h} mean RankIC")
        axes[j].legend(ncol=3)
    axes[1].set_xticks(range(30), [v["excluded_identity"] for v in values], rotation=90, fontsize=8)
    axes[1].set_xlabel("Excluded identity (diagnostic only; no refit, no industry removal)")
    save(
        fig,
        CHARTS[4],
        "All original industries remain in the research universe; only the evaluation cross-section changes.",
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle("Ranked-list concentration and adjacent-session turnover")
    for j, h in enumerate(("5", "10")):
        axes[0].bar(
            x + (j - 0.5) * 0.32,
            [models[s][h]["selection_concentration"]["top5"]["hhi"] for s in specs],
            0.32,
            label=f"H{h}",
            color=colors[j],
        )
        axes[1].bar(
            x + (j - 0.5) * 0.32,
            [models[s][h]["turnover"]["top5"]["mean"] for s in specs],
            0.32,
            label=f"H{h}",
            color=colors[j],
        )
    axes[0].axhline(1 / 30, color="#64748b", ls="--", label="Uniform 1/30")
    axes[0].set_ylabel("HHI of all top5 selections")
    axes[0].legend()
    axes[1].set_ylabel("Mean 1 - adjacent top5 overlap / 5")
    axes[1].legend()
    for ax in axes:
        ax.set_xticks(x, names, rotation=12)
    save(
        fig,
        CHARTS[5],
        "Top5 diagnostic; full top/bottom distributions are in the report. Raw spreads are not tradeable net profits.",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    render(args.public, args.preview)
