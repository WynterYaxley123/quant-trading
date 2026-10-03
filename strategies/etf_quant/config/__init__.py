"""Frozen product baseline; no research imports or provider-specific fields."""

BASELINE_COMMIT = "bd13d278b25eace66a7eae287307413f930effd9"
FACTORS_19 = (
    "d5",
    "d10",
    "d20",
    "d60",
    "d120",
    "p5",
    "p10",
    "p20",
    "p60",
    "p120",
    "align",
    "v5",
    "v20",
    "vc",
    "rev5",
    "rev10",
    "dd20",
    "dd60",
    "rsi",
)
H10_FACTORS = ("d10", "p5", "align", "vc", "dd20")
HORIZON_FACTORS = ((10, H10_FACTORS), (40, FACTORS_19), (120, FACTORS_19))
FUSION_WEIGHTS = ((10, 0.25), (40, 0.50), (120, 0.25))
TARGET_IDENTITY = "SAME_DATE_CROSS_SECTIONAL_EXCESS_FORWARD_RETURN"
MAPPING_CONTRACT_PENDING = "PENDING_DEEPSEEK_CONTRACT"
PUBLIC_INTEGRATION_REVIEW_PENDING = "PENDING_MIMO_AUDIT"
# Historical serialized values and imports remain compatible.
PENDING_DEEPSEEK_CONTRACT = MAPPING_CONTRACT_PENDING
PENDING_MIMO_AUDIT = PUBLIC_INTEGRATION_REVIEW_PENDING
INTEGRATION_DEPENDENCY_DEFERRED = "INTEGRATION_DEPENDENCY_DEFERRED"
