from pegel import model


def test_depth_formula():
    # Batin: Ruse at -114 cm -> 160 cm depth (offset 274)
    assert model.section_depths_cm({"ruse": -114, "svishtov": 0})["Batin"] == 160


def test_payload_table():
    assert model.payload_t(2.5) == 1500
    assert model.payload_t(0.4) == 0


def test_cost_matches_pro_danube():
    # Pro Danube convoy costs: EUR 23.48/t at 2.0 m vs EUR 14.85/t at 2.7 m -> ratio 1.58
    ratio = model.cost_per_t(2.0, 14.85) / model.cost_per_t(2.7, 14.85)
    assert abs(ratio - 23.48 / 14.85) < 0.05


def test_no_service_when_too_shallow():
    assert model.cost_per_t(1.0, 12) is None


def test_bottleneck_is_shallowest_section():
    d, section = model.max_draught_m({"ruse": -150, "svishtov": 100})
    assert section == "Batin"
