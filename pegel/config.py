"""Model constants. Route, section and gauge data live in data/*.csv, not here.

Every value says where it comes from. "PLACEHOLDER" = invented for the prototype;
see DATA_STATUS.md for the full list.
"""

# --- Barge: Europa IIb push barge (standard Danube push convoy barge) -----------------
# Draught (m) -> payload (t). Pro Danube 2013 operator data for 2.0-2.7 m;
# light draught ~0.5 m and max ~2,000 t at 3.0 m from Kiliya shipyard specs.
BARGE_TABLE = [(0.5, 0), (2.0, 1000), (2.3, 1250), (2.5, 1500), (2.7, 1750), (3.0, 2000)]
NORMAL_DRAUGHT_M = 2.7     # draught the trader's "normal" freight rate assumes
MIN_DRAUGHT_M = 1.0        # PLACEHOLDER: below this we report "no barge service" (barges still sail at 1.1-1.2 m in 2026, heavily underloaded)

UKC_CM = 25                # under-keel clearance; Contargo ~20 cm, RiverSat example 30 cm

# --- Cost -------------------------------------------------------------------------------
# Share of voyage cost fixed per trip; fitted to Pro Danube 2013 convoy costs (~0.77).
FIXED_COST_SHARE = 0.77

# Scarcity premium: in July 2026 barges loaded ~50 % and rates doubled (+100 %), while the
# physics above gives +77 %. The rest (~13 %) is market scarcity. Premium starts below
# SCARCITY_START load ratio and grows linearly: at 50 % load it adds ~13 %.
SCARCITY_START = 0.8
SCARCITY_SLOPE = 0.35      # premium share = SLOPE * (START - r) / START   (calibrated as above)

# --- Forecast -----------------------------------------------------------------------------
HISTORY_START_YEAR = 1996  # only recent years: the riverbed has dropped ~50-100 cm since the 1960s
ANOMALY_FADE_DAYS = 30     # today's departure from a past year fades with this e-folding time
NO_SERVICE_WARN = 0.10     # if >10 % of simulated runs have no service, the bad case is "no service"
