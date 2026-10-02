"""Synthetic pinned-upstream job receipts, never an online data test."""

import importlib.util
import sys
from contextlib import nullcontext
from datetime import date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def forward(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "services/cnequity-sidecar"))
    events = []
    (tmp_path / "lake").mkdir()

    def module(name, **attrs):
        m = ModuleType(name)
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, m)
        return m

    module(
        "runner",
        verify_install=lambda root: events.append("VERIFY_PIN"),
        lake_fingerprint=lambda root: "SYNTHETIC",
    )
    module("proxy_policy", proxy_policy=lambda p: nullcontext())
    module(
        "export_streaming",
        export_lake_streaming=lambda *a, **k: (
            events.append("EXPORT") or {"snapshot_id": "a" * 64}
        ),
    )
    dates = [date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)]
    package = module("cnequity")
    package.__path__ = []
    module(
        "cnequity.query",
        load=lambda *a, **k: SimpleNamespace(
            to_dicts=lambda: [{"trade_date": d, "is_trading": True} for d in dates]
        ),
    )
    module("cnequity.config", load_config=lambda p: SimpleNamespace(data_root=tmp_path / "lake"))
    job_status = {"status": "success"}

    class Engine:
        def __init__(self, cfg):
            datasets = [
                "trading_calendar",
                "instruments",
                "industry_members",
                "daily_bars",
                "index_bars",
                "corporate_actions",
                "trading_status",
            ]
            receipts = [
                {"dataset": d, "stage": s, "status": "success"}
                for d in datasets
                for s in ("fetch", "stage", "compact")
            ]
            receipts += [
                {"dataset": d, "stage": s, "status": "success"}
                for d, s in [
                    ("compact", "compact"),
                    ("adj_factors", "derive"),
                    ("adj_factors", "publish_revision"),
                    ("audit", "audit"),
                    ("trading_status_derive", "fetch"),
                    ("trading_status_derive", "stage"),
                ]
            ]
            self.manifest = SimpleNamespace(
                list_runs=lambda name: [], get_dataset_results=lambda run_id: receipts
            )

        def run_job(self, name, **kw):
            events.append((name, kw))
            return {"run_id": "SYNTHETIC_" + str(kw["trade_date"]), "status": job_status["status"]}

    module("cnequity.orchestrator.engine", JobEngine=Engine)
    steps = module("cnequity.steps")
    package.steps = steps
    from strategies.etf_quant.runtime.exports import SHANGHAI

    module("cnequity.domain.market_time", SHANGHAI_TZ=SHANGHAI)
    spec = importlib.util.spec_from_file_location(
        "synthetic_forward", ROOT / "services/cnequity-sidecar/forward.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    class Journal:
        def __init__(self, settings, after, sessions):
            self.cutoff = after
            self.latest = None

        def prepare(self, *args):
            pass

        def publish(self, session, result, run_id):
            self.cutoff = session
            self.latest = {**result, "session": str(session), "source_run_id": run_id}

    monkeypatch.setattr(m, "SessionJournal", Journal)
    monkeypatch.setattr(m, "enable_source_compatibility", lambda *a: {})
    monkeypatch.setattr(m, "scope_observation", lambda *a: {"missing_count": 0})
    config = tmp_path / "export.toml"
    config.write_text(
        '[paths]\nlake_root="'
        + (tmp_path / "lake").as_posix()
        + '"\n[export]\ncutoff="2026-09-24"\n'
    )
    return m, events, job_status, config


def test_forward_preserves_upstream_all_gates_and_exports_after_all_sessions(forward, tmp_path):
    m, events, status, config = forward
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        config,
        date(2026, 9, 29),
        date(2026, 9, 24),
        now=datetime.fromisoformat("2026-09-30T14:00:00+08:00"),
    )
    assert (
        result["status"] == "REFRESH_EXPORTED"
        and events[0] == "VERIFY_PIN"
        and events[-1] == "EXPORT"
    )
    jobs = [r for r in events if isinstance(r, tuple)]
    assert len(jobs) == 3 and all(r[1]["steps"] == m.STEPS for r in jobs)
    assert {"compact", "audit", "derive_adj_factors", "trading_status_derive"} <= set(m.STEPS)
    assert all("backfill" not in r[1] for r in jobs)


def test_unfinalized_success_gets_one_fresh_observation_when_provider_can_recover(
    forward, tmp_path, monkeypatch
):
    m, events, status, config = forward
    calls = []

    def run(engine, session, *, force_observation=False):
        calls.append(force_observation)
        return {
            "run_id": "SYNTHETIC",
            "status": "success",
            "action": "CURRENT_IDENTITY_REOBSERVATION"
            if force_observation
            else "REUSED_VERIFIED_JOB",
        }

    scopes = iter([{"missing_count": 1}, {"missing_count": 0}])
    monkeypatch.setattr(m, "session_job", run)
    monkeypatch.setattr(m, "scope_observation", lambda *a: next(scopes))
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        config,
        date(2026, 9, 29),
        date(2026, 9, 28),
        now=datetime.fromisoformat("2026-09-30T16:00:00+08:00"),
    )
    assert result["status"] == "REFRESH_EXPORTED" and calls == [False, True]
    assert result["receipts"][0]["action"] == "NEW_FORWARD_JOB_AFTER_UNFINALIZED_SCOPE"


def test_exception_after_published_session_preserves_finalized_pointer(
    forward, tmp_path, monkeypatch, capsys
):
    m, *_ = forward

    def fail(*args, observation, **kwargs):
        observation["latest_finalized"] = {"session": "2026-09-28", "snapshot_id": "a" * 64}
        raise TimeoutError("SYNTHETIC_PROVIDER_UNAVAILABLE")

    monkeypatch.setattr(m, "forward", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "forward.py",
            "--root",
            str(tmp_path),
            "--source-config",
            str(tmp_path / "source.toml"),
            "--export-config",
            str(tmp_path / "export.toml"),
            "--target",
            "2026-09-29",
            "--after",
            "2026-09-24",
        ],
    )
    m.main()
    import json

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "WAITING_FOR_PROVIDER_DATA"
    assert result["latest_finalized"]["session"] == "2026-09-28"


def test_upstream_failure_never_exports_or_invents_cutoff(forward, tmp_path):
    m, events, status, config = forward
    status["status"] = "failed"
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        config,
        date(2026, 9, 29),
        date(2026, 9, 24),
        now=datetime.fromisoformat("2026-09-30T14:00:00+08:00"),
    )
    assert result["status"] == "WAITING_FOR_PROVIDER_DATA" and "EXPORT" not in events
    assert len(result["receipts"]) == 1 and "snapshot_id" not in result


@pytest.mark.parametrize("target", [date(2026, 9, 30), date(2026, 10, 1)])
def test_unfinalized_current_or_future_session_never_fetches(forward, tmp_path, target):
    m, events, status, config = forward
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        config,
        target,
        date(2026, 9, 24),
        now=datetime.fromisoformat("2026-09-30T14:00:00+08:00"),
    )
    assert result["status"] == "WAITING_FOR_MARKET_CLOSE" and events == ["VERIFY_PIN"]


def test_missing_official_calendar_fails_closed(forward, tmp_path):
    m, events, status, config = forward
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        config,
        date(2026, 10, 1),
        date(2026, 9, 29),
        now=datetime.fromisoformat("2026-10-02T16:00:00+08:00"),
    )
    assert result["status"] == "BLOCKED_DATA_INTEGRITY" and events == ["VERIFY_PIN"]


def test_io_path_plumbing_preserves_identity_and_rejects_relative_or_other_lake(forward, tmp_path):
    m, *_ = forward
    root = tmp_path / "lake"
    cfg = SimpleNamespace(data_root=root)
    m.configure_io_root(cfg, {"lake_root": str(root)})
    assert cfg.data_root == root
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    m.configure_io_root(cfg, {"lake_root": str(root), "lake_io_root": str(alias)})
    assert cfg.data_root == alias and cfg.data_root.samefile(root)
    with pytest.raises(ValueError, match="ABSOLUTE"):
        m.configure_io_root(cfg, {"lake_root": str(root), "lake_io_root": "relative/lake"})
    other = tmp_path / "different"
    other.mkdir()
    with pytest.raises(ValueError, match="MISMATCH"):
        m.configure_io_root(cfg, {"lake_root": str(root), "lake_io_root": str(other)})


@pytest.mark.parametrize(
    "state,action,calls",
    [
        ("success", "REUSED_VERIFIED_JOB", 0),
        ("failed", "UPSTREAM_FAILED_BATCH_RECOVERY", 1),
        ("running", "EXISTING_JOB_NOT_TERMINAL", 0),
        ("degraded", "NEW_FORWARD_JOB_AFTER_DEGRADED", 1),
    ],
)
def test_only_own_exact_plan_is_reused_or_recovered(forward, state, action, calls):
    import json

    m, *_ = forward
    events = []
    session = date(2026, 9, 28)
    row = {
        "job_name": m.JOB,
        "run_id": "SYNTHETIC_OWN",
        "status": state,
        "metadata_json": json.dumps(
            {"trade_date": str(session), "backfill": False, "planned_steps": m.STEPS}
        ),
    }
    engine = SimpleNamespace(
        manifest=SimpleNamespace(list_runs=lambda name: [row]),
        run_job=lambda name, **kw: (
            events.append((name, kw)) or {"run_id": "SYNTHETIC_OWN", "status": "success"}
        ),
    )
    result = m.session_job(engine, session)
    assert result["action"] == action and len(events) == calls
    if calls and state == "failed":
        assert (
            events[0][1]["run_id"] == "SYNTHETIC_OWN" and events[0][1]["retry_failed_only"] is True
        )
    if state == "degraded":
        assert "run_id" not in events[0][1] and "retry_failed_only" not in events[0][1]
        assert events[0][1]["steps"] == m.STEPS
    if state == "running":
        assert result["status"] == "pending"


def test_mismatched_plan_cannot_be_adopted(forward):
    import json

    m, *_ = forward
    session = date(2026, 9, 28)
    row = {
        "job_name": m.JOB,
        "run_id": "SYNTHETIC_UNKNOWN",
        "status": "success",
        "metadata_json": json.dumps(
            {"trade_date": str(session), "backfill": True, "planned_steps": m.STEPS}
        ),
    }
    engine = SimpleNamespace(
        manifest=SimpleNamespace(list_runs=lambda name: [row]),
        run_job=lambda *a, **k: pytest.fail("unknown job must never be invoked"),
    )
    with pytest.raises(ValueError, match="PLAN_IDENTITY"):
        m.session_job(engine, session)


def test_degraded_source_is_a_data_wait_never_a_partial_export(forward, tmp_path):
    m, events, status, config = forward
    status["status"] = "degraded"
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        config,
        date(2026, 9, 29),
        date(2026, 9, 24),
        now=datetime.fromisoformat("2026-09-30T16:00:00+08:00"),
    )
    assert result["status"] == "WAITING_FOR_PROVIDER_DATA" and "EXPORT" not in events
    assert result["receipts"][0]["status"] == "degraded"
    assert "unready_stages" in result["receipts"][0] and "snapshot_id" not in result


def test_windows_raw_path_gate_covers_resolved_long_root_and_extended_globs(forward):
    m, *_ = forward
    m.windows_storage_path_gate(r"D:\QuantForge\etf-lake")
    with pytest.raises(ValueError, match="SHORT_PHYSICAL"):
        m.windows_storage_path_gate(r"D:\QuantForge\external\cnequity-etf-quant-v1\lake-minimal")
    with pytest.raises(ValueError, match="NORMAL_ABSOLUTE"):
        m.windows_storage_path_gate("\\\\?\\D:\\QuantForge\\etf-lake")


def test_latest_failure_never_hides_successful_receipt_for_same_session(forward):
    import json

    m, *_ = forward
    session = date(2026, 9, 28)

    def row(status):
        return {
            "status": status,
            "job_name": m.JOB,
            "run_id": "SYNTHETIC_" + status,
            "metadata_json": json.dumps(
                {"trade_date": str(session), "backfill": False, "planned_steps": m.STEPS}
            ),
        }

    engine = SimpleNamespace(
        manifest=SimpleNamespace(
            list_runs=lambda job: [row("failed"), row("success"), row("degraded")]
        ),
        run_job=lambda *a, **k: pytest.fail("must reuse admitted success, not latest failure"),
    )
    assert m.session_job(engine, session)["run_id"] == "SYNTHETIC_success"


def test_later_failure_returns_previously_finalized_session_without_exporting_failed_day(
    forward, tmp_path
):
    m, events, status, cfg = forward
    calls = []

    def job(engine, session, **kwargs):
        calls.append(session)
        return {
            "status": "success" if len(calls) == 1 else "failed",
            "run_id": "SYNTHETIC_" + str(session),
            "action": "NEW_FORWARD_JOB",
        }

    m.session_job = job
    result = m.forward(
        tmp_path,
        tmp_path / "source.toml",
        cfg,
        date(2026, 9, 29),
        date(2026, 9, 24),
        now=datetime.fromisoformat("2026-09-30T16:00:00+08:00"),
    )
    assert result["status"] == "WAITING_FOR_PROVIDER_DATA"
    assert result["latest_finalized"]["session"] == "2026-09-25"
    assert (
        events.count("EXPORT") == 1 and len(calls) == 2
    )  # synthetic calendar; never guessed weekdays


def test_wrapped_local_path_failure_cannot_be_labelled_provider_wait(forward):
    m, *_ = forward
    leaf = ValueError("SYNTHETIC_UNSAFE_PATH")
    outer = RuntimeError("SYNTHETIC_PROVIDER_WRAPPER")
    outer.__cause__ = leaf
    assert m.exception_status(outer) == ("BLOCKED_DATA_INTEGRITY", "LOCAL_ENGINEERING_FAILURE")
    assert m.exception_status(TimeoutError("SYNTHETIC_TIMEOUT")) == (
        "WAITING_FOR_PROVIDER_DATA",
        "PROVIDER_DATA_FAILURE",
    )
