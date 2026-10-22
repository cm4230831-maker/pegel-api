"""All numbers the model uses live here. Every value says where it came from.
Values marked CALIBRATE are placeholders: replace them with real data before the demo."""

# --- Route: Lom/Ruse -> Constanta -------------------------------------------
# Critical shallow sections on the route. Depth (cm) = gauge reading (cm) + offset_cm.
# How to calibrate an offset: take the depth APPD reports for the section on a day,
# subtract that same day's gauge reading. Use the median of several days.
SECTIONS = [
    # Batin: Aug 2026 min depth ~160 cm while Ruse read ~-114 cm  ->  160 - (-114) = 274
    {"name": "Batin", "river_km": 528, "gauge": "ruse", "offset_cm": 274},
    # Belene: CALIBRATE with APPD depth vs Svishtov reading (placeholder value)
    {"name": "Belene", "river_km": 563, "gauge": "svishtov", "offset_cm": 230},
]

# Gauges the model needs (history files in data/history/<id>.csv)
GAUGES = {
    "ruse": {"name": "Ruse", "river_km": 495},
    "svishtov": {"name": "Svishtov", "river_km": 554},
}

TRANSIT_DAYS = 4          # days a convoy spends passing the critical sections (CALIBRATE)

# --- Barge: Europa IIb push barge ---------------------------------------------
# Draught (m) -> payload (t). Operator data, Pro Danube 2013 (2.0-2.7 m);
# light draught ~0.5 m and max ~2,000 t at 3.0 m from shipyard specs.
BARGE_TABLE = [(0.5, 0), (2.0, 1000), (2.3, 1250), (2.5, 1500), (2.7, 1750), (3.0, 2000)]
NORMAL_DRAUGHT_M = 2.7    # draught the trader's "normal" freight rate assumes
MIN_DRAUGHT_M = 1.3       # below this we say "no barge service" (CALIBRATE)

UKC_CM = 25               # under-keel clearance; Contargo uses ~20 cm, RiverSat example 30 cm

# --- Cost -----------------------------------------------------------------------
# Share of voyage cost that is fixed per trip. Fit to Pro Danube convoy costs: ~0.77
FIXED_COST_SHARE = 0.77

# --- History ----------------------------------------------------------------------
HISTORY_START_YEAR = 1996  # use only recent years: the riverbed has eroded since
