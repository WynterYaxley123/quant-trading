"""Run reproducible synthetic comparisons; times are observations, never CI thresholds."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
import pandas as pd

from benchmarks import fixtures, reference
from benchmarks.lake import fingerprint_function
from research.development_panel import DevelopmentPanel
from strategies.etf_quant.mapping.liquidity import LiquidityLookup, assess_liquidity
from strategies.etf_quant.runtime.industry import build_industry_series
from strategies.etf_quant.runtime.prediction import TrainingInputs, training_rows
from strategies.etf_quant.runtime.prefix import SourcePrefixIndex, source_prefix
from strategies.sw_sector_rotation.src.model.model import CrossSectionalRidgeModel
from strategies.sw_sector_rotation.src.strategy import SWSectorRotationCore


def compare(hotspot, scale, baseline, optimized, *, equivalent, algorithms, note, memory):
    before, after = [], []
    for _ in range(3):
        start = perf_counter()
        expected = baseline()
        before.append(perf_counter() - start)
        start = perf_counter()
        actual = optimized()
        after.append(perf_counter() - start)
        equivalent(expected, actual)
    left, right = statistics.median(before), statistics.median(after)
    return {
        "hotspot": hotspot,
        "synthetic_scale": scale,
        "baseline_algorithm": algorithms[0],
        "optimized_algorithm": algorithms[1],
        "baseline_seconds": left,
        "optimized_seconds": right,
        "speedup": left / right,
        "output_equivalence": "PASS",
        "asymptotic_note": note,
        "memory": memory,
        "repetitions": 3,
        "statistic": "median",
    }


def exact(expected, actual):
    assert expected == actual


def industry_equal(expected, actual):
    pd.testing.assert_frame_equal(expected.closes, actual.closes, check_exact=True)
    assert expected.audit == actual.audit


def panel_equal(expected, actual):
    for panels_a, panels_b in zip(expected, actual):
        for code in panels_a:
            pd.testing.assert_frame_equal(panels_a[code], panels_b[code], atol=1e-12, rtol=1e-12)


def run():
    records = []
    for sectors in (20, 100):
        provider = fixtures.industry(50, sectors)
        records.append(
            compare(
                "industry",
                {"days": 50, "industries": sectors, "constituents": 6},
                lambda provider=provider: reference.build_industry_series(
                    provider, classification_version="SYNTHETIC"
                ),
                lambda provider=provider: build_industry_series(
                    provider, classification_version="SYNTHETIC"
                ),
                equivalent=industry_equal,
                algorithms=("per-industry full membership scan", "snapshot industry index"),
                note="Membership lookup O(D*I*C) -> O(C log C + D*C); price validation still O(D*C).",
                memory="O(C) grouped membership index; price/audit storage unchanged.",
            )
        )
    for etfs in (8, 40):
        provider = fixtures.liquidity(etfs)
        window = provider.sessions[-20:]
        codes = list(provider.tables["instruments"].symbol)

        def admitted(provider=provider, codes=codes, window=window):
            lookup = LiquidityLookup.build(provider.tables)
            return [assess_liquidity(provider, c, window, lookup=lookup) for c in codes]

        records.append(
            compare(
                "liquidity",
                {"etfs": etfs, "bars": 40 * etfs, "window": 20},
                lambda provider=provider, codes=codes, window=window: [
                    reference.assess_liquidity(provider, c, window) for c in codes
                ],
                admitted,
                equivalent=exact,
                algorithms=(
                    "repeated full-frame boolean scans",
                    "one grouped index + keyed windows",
                ),
                note="O(E*W*N) scans -> O(N+E*W); index build included.",
                memory="O(N) row index; duplicates retained.",
            )
        )
    for sectors in (8, 24):
        series, provider, features, config = fixtures.prediction(sectors=sectors)

        def assembled(series=series, provider=provider, features=features, config=config):
            inputs = TrainingInputs.build(series, series.universe, features, config.horizons)
            return [
                training_rows(series, provider, s, series.universe, features, inputs=inputs)
                for s in config.horizons
            ]

        records.append(
            compare(
                "prediction",
                {"days": 420, "sectors": sectors, "horizons": 3},
                lambda series=series, provider=provider, features=features, config=config: [
                    reference.training_rows(series, provider, s, series.universe, features)
                    for s in config.horizons
                ],
                assembled,
                equivalent=exact,
                algorithms=("per-date/horizon pandas selection", "shared ordered NumPy arrays"),
                note="Hoisted close/feature projection; maturity and observation order identical.",
                memory="O(D*I*F) read-only call-scoped arrays; no long-lived model cache.",
            )
        )
    frames, cal = fixtures.market(600, 6)
    core = SWSectorRotationCore()
    signals = list(range(400, 420))

    def old_panels():
        return [
            core.build_panel(
                {c: f.iloc[i - 350 : i + 1] for c, f in frames.items()},
                include_rsrs=False,
                calendar=cal[i - 350 : i + 1].tolist(),
            )
            for i in signals
        ]

    def new_panels():
        cache = DevelopmentPanel(frames, cal[signals[-1]])
        return [cache.visible(cal[i - 350], cal[i], (10, 40, 120)) for i in signals]

    records.append(
        compare(
            "research_rolling",
            {"sectors": 6, "signal_dates": 20, "visible_days": 351},
            old_panels,
            new_panels,
            equivalent=panel_equal,
            algorithms=(
                "rebuild finite rolling factors every signal",
                "one causal panel + visible labels/warmup masks",
            ),
            note="Factor construction O(S*I*D*F) -> O(I*D*F); slicing/label tails remain per signal.",
            memory="O(I*D*F) bounded to last Development signal; no sealed dates.",
        )
    )
    cache = SourcePrefixIndex()
    provider = fixtures.industry(120, 50)
    records.append(
        compare(
            "shadow_prefix_cold",
            {"stock_rows": 36000, "total_rows": 36600, "industries": 50, "days": 120},
            lambda: reference.source_prefix(provider),
            lambda: source_prefix(provider, index=SourcePrefixIndex()),
            equivalent=exact,
            algorithms=("row byte authentication", "content and row byte authentication"),
            note="Cold calls authenticate content and rebuild all row hashes; no cross-process reuse claim.",
            memory="One result per dataset O(N); a canonical byte buffer is temporary.",
        )
    )
    source_prefix(provider, index=cache)  # Explicit warm repeated-cycle comparison.
    records.append(
        compare(
            "shadow_prefix_warm",
            {"stock_rows": 36000, "total_rows": 36600, "industries": 50, "days": 120},
            lambda: reference.source_prefix(provider),
            lambda: source_prefix(provider, index=cache),
            equivalent=exact,
            algorithms=(
                "N row serializations + SHA256 calls",
                "content SHA256 + authenticated in-process row-hash reuse",
            ),
            note="Both examine all economic bytes O(N); warm row-hash calls N -> 0. New process/cold misses recompute rows.",
            memory="One result per dataset O(N); temporary canonical content buffer; caller receives isolated copies.",
        )
    )
    label_panel = core.build_panel(frames, include_rsrs=False, calendar=cal.tolist())
    first, last = cal[300], cal[420]

    def old_dates():
        sets = [set(f.dropna(subset=["fwd40"]).index) for f in label_panel.values()]
        return [d for d in sorted(set.intersection(*sets)) if first <= d <= last]

    def new_dates():
        sets = [set(f.loc[first:last, "fwd40"].dropna().index) for f in label_panel.values()]
        return sorted(set.intersection(*sets))

    records.append(
        compare(
            "training_dates",
            {"sectors": 6, "frame_days": 600, "train_days": 121},
            old_dates,
            new_dates,
            equivalent=exact,
            algorithms=(
                "full-factor-frame dropna per horizon",
                "date-slice and label-only validity",
            ),
            note="Validity work O(I*D*F) -> O(I*T), with T the eligible window.",
            memory="Only eligible label-date sets; sample selection unchanged.",
        )
    )
    train_dates = cal[300:421].tolist()

    def old_training():
        model = CrossSectionalRidgeModel()
        fitted = reference.fit_period_reference(
            model, "medium", label_panel, core.feature_names, train_dates
        )
        return fitted.coef_, fitted.intercept_, model.training_coverage

    def new_training():
        model = CrossSectionalRidgeModel()
        fitted = model.fit_period("medium", label_panel, core.feature_names, train_dates)
        return fitted.coef_, fitted.intercept_, model.training_coverage

    def training_equal(left, right):
        np.testing.assert_array_equal(left[0], right[0])
        assert left[1:] == right[1:]

    records.append(
        compare(
            "training_assembly",
            {
                "sectors": 6,
                "frame_days": 600,
                "train_days": 121,
                "features": len(core.feature_names),
            },
            old_training,
            new_training,
            equivalent=training_equal,
            algorithms=(
                "full index masks and repeated frame validity work",
                "index positions and one projected validity array",
            ),
            note="Date lookup O(I*D) -> O(I*T); selected sample and matrix layout preserved. Ridge fit still O(P cubed).",
            memory="Combined validity projection O(I*T*P); retain Pandas matrix layout for exact BLAS results.",
        )
    )
    # Mutable upstream lake has no authenticated immutable per-file identity.
    # Hash every byte; timestamp/size caches would miss same-size restored-mtime tampering.
    with TemporaryDirectory(prefix="synthetic-lake-") as directory:
        lake = Path(directory)
        for i in range(12):
            p = lake / "curated" / f"{i:02d}.parquet"
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(bytes([i]) * 262144)

        lake_digest = fingerprint_function()

        def fingerprint():
            return lake_digest(lake)

        records.append(
            compare(
                "lake_fingerprint",
                {"files": 12, "bytes": 12 * 262144},
                fingerprint,
                fingerprint,
                equivalent=exact,
                algorithms=("full byte authentication", "retained full byte authentication"),
                note="NO_CHANGE: mutable lake lacks authenticated immutable child identities. Safe lower bound O(bytes).",
                memory="Production streams 1 MiB blocks; no unsafe persistent hash cache.",
            )
        )
    return {
        "synthetic_only": True,
        "market_data_read": False,
        "base_sha": "1e2ffbd4f75120df2511472662dcf7dcd308b0d6",
        "timing_gate": False,
        "comparisons": records,
    }


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
