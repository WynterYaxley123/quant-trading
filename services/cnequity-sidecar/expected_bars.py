"""Report the pinned ownership contract; never infer a halt from a missing bar."""
from pathlib import Path
from strategies.etf_quant.runtime.storage import atomic_bytes, json_bytes


def classify(expected, received, explicit_no_bar=()):
    expected, received, explicit_no_bar = set(expected), set(received), set(explicit_no_bar)
    missing = sorted(expected - received - explicit_no_bar)
    return {"expected_count": len(expected - explicit_no_bar),
            "received_count": len((expected - explicit_no_bar) & received),
            "missing_count": len(missing), "missing_sample": missing[:8],
            "expected_no_bar_count": len(explicit_no_bar),
            "classification": "PROVIDER_DATA_FAILURE" if missing else "EXPECTED_MARKET_STATE",
            "reason_code": "PROVIDER_MISSING" if missing else "EXPECTED_SCOPE_SATISFIED",
            "retryable": bool(missing)}, missing


def observe(cfg, run_id, session):
    import polars as pl
    from cnequity.query import load
    from cnequity.steps.common import load_symbols
    from cnequity.domain.symbols import filter_ingest_universe
    from cnequity.steps.bars import _classify_daily_scope, _instrument_spans, _placeholder_bar_universe
    from cnequity.storage import StagingWriter
    symbols = filter_ingest_universe(load_symbols(cfg), cfg.ingest_universe)
    ownership = _classify_daily_scope(cfg, symbols, session, session,
        bar_universe=_placeholder_bar_universe(cfg, _instrument_spans(cfg)))
    expected = ownership.generic + ownership.unknown + ownership.delegated_delisted
    bars = load("daily_bars", start=str(session), end=str(session), data_root=cfg.data_root, adjust=None)
    received = set(bars["symbol"].to_list()) if bars.height else set()
    staged = StagingWriter(cfg.staging_root).list_run_files("daily_bars", run_id)
    for path in staged:
        frame = pl.read_parquet(path)
        received.update(frame.filter(pl.col("trade_date") == session)["symbol"].to_list())
    summary, missing = classify(expected, received, ownership.expected_no_data)
    artifact = cfg.meta_root / "etf_quant_scope" / run_id / (str(session) + ".json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(artifact, json_bytes({"session": str(session), "expected_symbols": sorted(set(expected)),
        "received_symbols": sorted(received), "missing_symbols": missing,
        "explicit_no_bar_reasons": ownership.no_data_reasons,
        "placeholders_not_claimed_as_suspensions": ownership.placeholder, "summary": summary}))
    return {**summary, "source": "PINNED_CNEQUITY_TDX_BSE_AND_EXISTING_CONTRACT_SOURCES",
            "stage": "daily_bars_completeness", "scope_artifact_id": run_id + "/" + str(session),
            "next_action": "RERUN_ONE_SHOT" if missing else "CONTINUE_ADMISSION"}
