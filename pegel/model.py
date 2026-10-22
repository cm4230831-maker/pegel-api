"""Steps 1-3: water level -> depth -> draught -> tonnes -> EUR per tonne.

Methods and sources: see the "Pegel - Calculation Methods" doc and DATA_STATUS.md.
"""
import math

import numpy as np

from pegel import config


def section_depth_cm(level_cm: float, offset_cm: float) -> float:
    """Step 1. Depth at a shallow spot = reading of its reference gauge + fixed offset.
    This is how APPD itself computes depths (constant offset per section)."""
    return level_cm + offset_cm


def draught_m(depth_cm: float) -> float:
    """Step 2a. Max draught = depth at the shallowest spot - under-keel clearance."""
    return (depth_cm - config.UKC_CM) / 100


def payload_t(draught: float) -> float:
    """Step 2b. Tonnes one Europa IIb barge carries at this draught."""
    xs = [d for d, _ in config.BARGE_TABLE]
    ys = [t for _, t in config.BARGE_TABLE]
    return float(np.interp(draught, xs, ys))


def load_ratio(draught: float) -> float:
    d = min(draught, config.NORMAL_DRAUGHT_M)
    return payload_t(d) / payload_t(config.NORMAL_DRAUGHT_M)


def scarcity_share(r: float) -> float:
    """Extra market premium when barges load little (calibrated on July 2026)."""
    if r >= config.SCARCITY_START:
        return 0.0
    return config.SCARCITY_SLOPE * (config.SCARCITY_START - r) / config.SCARCITY_START


def cost_breakdown(draught: float, normal_rate: float) -> dict | None:
    """Step 3. EUR/t at this draught; None = no barge service.
        physical = R_normal * (a + (1 - a) r) / r       a = fixed cost share, r = load ratio
        total    = physical * (1 + scarcity)"""
    if draught < config.MIN_DRAUGHT_M:
        return None
    r = load_ratio(draught)
    a = config.FIXED_COST_SHARE
    physical = normal_rate * (a + (1 - a) * r) / r
    scarcity = physical * scarcity_share(r)
    return {"total": physical + scarcity, "physical": physical, "scarcity": scarcity, "load_ratio": r}


def cost_per_t(draught: float, normal_rate: float) -> float | None:
    b = cost_breakdown(draught, normal_rate)
    return None if b is None else b["total"]


def barges_needed(quantity_t: float, draught: float) -> int | None:
    if draught < config.MIN_DRAUGHT_M:
        return None
    return math.ceil(quantity_t / payload_t(min(draught, config.NORMAL_DRAUGHT_M)))


def breakeven_draught(normal_rate: float, alternative_rate: float) -> float | None:
    """Draught below which the alternative (rail/truck) is cheaper than the barge."""
    for d in np.arange(config.NORMAL_DRAUGHT_M, config.MIN_DRAUGHT_M - 0.001, -0.01):
        c = cost_per_t(float(d), normal_rate)
        if c is None or c >= alternative_rate:
            return round(float(d), 2)
    return None
