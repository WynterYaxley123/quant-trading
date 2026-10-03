"""One invocation of the formal cycle; factual WAIT creates no failed epoch."""

from .formal import start_gate
from .shadow import daily_cycle
from .storage import GateError


def one_shot(
    provider, registry, runtime_root, *, now, code_commit, formal_contract, pit_evidence, **kwargs
):
    try:
        gate = start_gate(provider, formal_contract, now)
        if gate != "ELIGIBLE":
            return {
                "status": gate,
                "shadow_epoch_created": False,
                "validation_opened": False,
                "final_oos_read": False,
                "data_cutoff": str(provider.cutoff),
            }
        result = daily_cycle(
            provider,
            registry,
            runtime_root,
            now=now,
            code_commit=code_commit,
            formal_contract=formal_contract,
            pit_evidence=pit_evidence,
            execution_policy="B40_WITH_CASH",
            **kwargs,
        )
        return {
            **result,
            "lifecycle_state": result["status"],
            "status": "ALREADY_PROCESSED"
            if result["status"] == "IDEMPOTENT_NO_CHANGE"
            else "STARTED",
        }
    except GateError as error:
        waiting = {
            "FORMAL_SIGNAL_NOT_ACCEPTED": "READY_NO_SIGNAL",
            "MODEL_WARMUP_INCOMPLETE": "WAITING_FOR_DATA",
            "INSUFFICIENT_INDUSTRY_UNIVERSE": "WAITING_FOR_DATA",
            "SOURCE_C_INPUT_BLOCKER": "WAITING_FOR_DATA",
            "CURRENT_FINALIZED_SESSION_REQUIRED": "WAITING_FOR_FINALIZED_DATA",
        }
        return {
            "status": waiting.get(error.code, "BLOCKED_INTEGRITY"),
            "blocker": error.code,
            "validation_opened": False,
            "final_oos_read": False,
        }
