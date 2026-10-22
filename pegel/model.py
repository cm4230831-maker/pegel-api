"""Steps 1-3: water level -> depth -> draught -> tonnes -> EUR per tonne."""
import math

import numpy as np

from pegel import config


def section_depths_cm(levels_cm: dict) -> dict:
    """Step 1. levels_cm = {"ruse": -114, "svishtov": -60} -> {"Batin": 160, ...}"""
    return {s["name"]: levels_cm[s["gauge"]] + s["offset_cm"] for s in config.SECTIONS}


def max_draught_m(levels_cm: dict) -> tuple[float, str]:
    """Step 2a. The shallowest section on the route limits the convoy."""
    depths = section_depths_cm(levels_cm)
    bottleneck = min(depths, key=depths.get)
    return (depths[bottleneck] - config.UKC_CM) / 100, bottleneck


def payload_t(draught_m: float) -> float:
    """Step 2b. Tonnes one barge can carry at this draught."""
    xs = [d for d, _ in config.BARGE_TABLE]
    ys = [t for _, t in config.BARGE_TABLE]
    return float(np.interp(draught_m, xs, ys))


def cost_per_t(draught_m: float, normal_rate_eur_t: float) -> float | None:
    """Step 3. EUR/t at this draught. None = no barge service.

    Most voyage cost is fixed per trip, so cost per tonne rises as the load falls:
        R = R_normal * (a + (1 - a) * r) / r,   r = payload / normal payload
    """
    if draught_m < config.MIN_DRAUGHT_M:
        return None
    draught_m = min(draught_m, config.NORMAL_DRAUGHT_M)  # never cheaper than the normal rate
    r = payload_t(draught_m) / payload_t(config.NORMAL_DRAUGHT_M)
    a = config.FIXED_COST_SHARE
    return normal_rate_eur_t * (a + (1 - a) * r) / r


def barges_needed(quantity_t: float, draught_m: float) -> int | None:
    p = payload_t(draught_m)
    return math.ceil(quantity_t / p) if p > 0 else None


def rail_breakeven(normal_rate_eur_t: float, rail_eur_t: float) -> dict | None:
    """Draught (and bottleneck gauge level) below which rail is cheaper."""
    for d in np.arange(config.NORMAL_DRAUGHT_M, config.MIN_DRAUGHT_M - 0.001, -0.01):
        c = cost_per_t(float(d), normal_rate_eur_t)
        if c is None or c >= rail_eur_t:
            draught = round(float(d), 2)
            # express it as a gauge reading at each section's reference gauge
            levels = {
                s["name"]: {"gauge": s["gauge"],
                            "level_cm": round(draught * 100 + config.UKC_CM - s["offset_cm"])}
                for s in config.SECTIONS
            }
            return {"draught_m": draught, "gauge_levels": levels}
    return None  # barge stays cheaper than rail down to the service limit
