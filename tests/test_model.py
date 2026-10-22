from datetime import date

from fastapi.testclient import TestClient

import main
from pegel import config, data, model

client = TestClient(main.app)


def test_cost_matches_pro_danube():
    # Pro Danube 2013: EUR 23.48/t at 2.0 m vs EUR 14.85/t at 2.7 m -> ratio 1.58 (physical part)
    b20, b27 = model.cost_breakdown(2.0, 14.85), model.cost_breakdown(2.7, 14.85)
    assert abs(b20["physical"] / b27["physical"] - 23.48 / 14.85) < 0.05


def test_scarcity_matches_july_2026():
    # ~50 % load -> total about double the normal rate (+100 %)
    d = 1.85  # payload ~875 t = 50 % of 1750 t
    assert 1.85 < model.cost_per_t(d, 10) / 10 < 2.15


def test_no_service_below_min_draught():
    assert model.cost_per_t(config.MIN_DRAUGHT_M - 0.01, 12) is None
    assert model.barges_needed(3000, config.MIN_DRAUGHT_M - 0.01) is None


def test_today_matches_appd():
    # APPD on 22 Oct 2026: Albina island deepest lane 138 cm with Silistra at -142 cm
    s = data.sections().set_index("section").loc["Albina island"]
    assert model.section_depth_cm(-142, s.offset_cm) == 138


def test_every_route_quotes():
    for rid in data.routes().index:
        r = client.post("/quote", json={"route": rid, "window_start": "2026-11-10", "window_end": "2026-11-20"})
        assert r.status_code == 200, (rid, r.text)
        assert r.json()["summary"]["no_service_probability"] >= 0


def test_replay_2022():
    r = client.post("/quote", json={"route": "lom-constanta", "today": "2022-06-15",
                                    "window_start": "2022-08-01", "window_end": "2022-08-20"})
    assert r.status_code == 200, r.text


def test_bad_route_is_400():
    r = client.post("/quote", json={"route": "nowhere", "window_start": "2026-11-10", "window_end": "2026-11-20"})
    assert r.status_code == 400
