"""Regression tests for the PrintHive multi-printer planning extension."""

import json
from pathlib import Path
import sys

# Run from repository root (as instructed in README).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import PrintJob
import pytest
from fleet_scheduler import (
    Printer, Requirements, compatible, fits,
    load_fleet_settings, plan_fleet,
)


def printer(name="printer-a", material="PLA", size=(250, 210, 220), online=True, at=0):
    return Printer(name, size, frozenset({material}), material, online, at)


def spec(material="PLA", size=(100, 100, 40)):
    return Requirements(material, size)


def job(job_id=1, weight=10, submit=0, duration=600, cancelled=False):
    return PrintJob(job_id, weight, submit, duration, cancelled)


def test_two_printers_can_print_simultaneously():
    jobs = [job(1), job(2)]
    fleet = [printer("p1"), printer("p2")]
    result = plan_fleet(jobs, fleet, {"1": spec(), "2": spec()}, buffer_time=0)
    assert {a["printer_id"] for a in result["assignments"]} == {"p1", "p2"}
    assert [a["start_time"] for a in result["assignments"]] == [0, 0]


def test_uses_teammates_priority_scoring():
    jobs = [job(1, weight=3), job(2, weight=20)]
    result = plan_fleet(jobs, [printer()], {"1": spec(), "2": spec()}, buffer_time=0)
    assert [a["job_id"] for a in result["assignments"]] == [2, 1]


def test_print_does_not_start_before_job_arrives():
    jobs = [job(1, submit=3600)]
    result = plan_fleet(jobs, [printer()], {"1": spec()})
    assert result["assignments"][0]["start_time"] == 3600


def test_busy_printer_is_reserved_until_its_release_time():
    result = plan_fleet([job(1)], [printer(at=2400)], {"1": spec()})
    assert result["assignments"][0]["start_time"] == 2400


def test_bed_clearance_buffer_prevents_instant_reuse():
    result = plan_fleet([job(1), job(2)], [printer()], {"1": spec(), "2": spec()}, buffer_time=200)
    assert [a["start_time"] for a in result["assignments"]] == [0, 800]


def test_material_must_be_supported_and_loaded():
    requirement = spec(material="PETG")
    assert not compatible(printer(), requirement)
    result = plan_fleet([job(1)], [printer()], {"1": requirement})
    assert result["unassigned"] == [{"job_id": 1, "reason": "material_unsupported"}]


def test_supported_material_not_loaded_is_flagged():
    p = Printer("bambu", (256, 256, 256), frozenset({"PLA", "PETG"}), "PLA")
    result = plan_fleet([job(1)], [p], {"1": spec("PETG")})
    assert result["unassigned"][0]["reason"] == "material_not_loaded"


def test_print_must_fit_all_three_oriented_dimensions():
    p = printer(size=(200, 200, 200))
    assert not fits(p, spec(size=(100, 100, 205)))
    result = plan_fleet([job(1)], [p], {"1": spec(size=(100, 100, 205))})
    assert result["unassigned"][0]["reason"] == "exceeds_build_volume"


def test_offline_printer_never_gets_assigned():
    result = plan_fleet([job(1)], [printer(online=False)], {"1": spec()})
    assert not result["assignments"]
    assert result["unassigned"][0]["reason"] == "no_online_printers"


def test_bigger_offline_printer_does_not_allow_oversized_job():
    fleet = [printer("small", size=(150, 150, 150)), printer("large", size=(300, 300, 300), online=False)]
    result = plan_fleet([job(1)], fleet, {"1": spec(size=(200, 200, 200))})
    assert result["unassigned"][0]["reason"] == "exceeds_build_volume"


def test_preserves_large_only_printer_for_large_job():
    small = printer("small", size=(120, 120, 120))
    large = printer("large", size=(250, 250, 250))
    jobs = [job(1, weight=100), job(2, weight=1)]
    requirements = {"1": spec(size=(60, 60, 60)), "2": spec(size=(200, 200, 200))}
    result = plan_fleet(jobs, [large, small], requirements)
    assignments = {a["job_id"]: a["printer_id"] for a in result["assignments"]}
    assert assignments == {1: "small", 2: "large"}
    assert all(a["start_time"] == 0 for a in result["assignments"])


def test_cancellation_is_skipped_even_if_no_metadata_available():
    result = plan_fleet([job(1, cancelled=True)], [printer()], {})
    assert result["assignments"] == []
    assert result["unassigned"] == [{"job_id": 1, "reason": "cancelled"}]


def test_now_never_schedules_in_the_past():
    result = plan_fleet([job(1, submit=0)], [printer(at=100)], {"1": spec()}, now=2000)
    assert result["assignments"][0]["start_time"] == 2000


def test_no_jobs_yields_empty_valid_json_result():
    result = plan_fleet([], [printer()], {})
    assert result["summary"]["jobs_assigned"] == 0
    assert result["summary"]["average_wait_s"] == 0
    json.dumps(result)


def test_missing_sliced_metadata_is_rejected():
    with pytest.raises(ValueError, match="Missing sliced"):
        plan_fleet([job(1)], [printer()], {})


def test_duplicate_job_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate job_id"):
        plan_fleet([job(1), job(1)], [printer()], {"1": spec()})


def test_duplicate_printers_are_rejected():
    with pytest.raises(ValueError, match="Duplicate printer_id"):
        plan_fleet([job(1)], [printer(), printer()], {"1": spec()})


@pytest.mark.parametrize("bad_alpha", [-0.1, float("nan"), float("inf")])
def test_invalid_aging_factors_are_rejected(bad_alpha):
    with pytest.raises(ValueError, match="alpha"):
        plan_fleet([job(1)], [printer()], {"1": spec()}, alpha=bad_alpha)


def test_negative_buffer_is_rejected():
    with pytest.raises(ValueError, match="buffer_time"):
        plan_fleet([job(1)], [printer()], {"1": spec()}, buffer_time=-1)


def test_invalid_job_duration_is_rejected():
    with pytest.raises(ValueError, match="print_duration"):
        plan_fleet([job(1, duration=0)], [printer()], {"1": spec()})


def test_load_fleet_demo_file():
    root = Path(__file__).resolve().parents[1]
    fleet, requirements = load_fleet_settings(root / "fleet_demo.json")
    assert len(fleet) == 4
    assert requirements["102"].dimensions_mm == (220.0, 190.0, 100.0)


def test_load_fleet_rejects_duplicate_id(tmp_path):
    raw = {
        "printers": [
            {"printer_id": "p", "build_volume_mm": [200, 200, 200], "supported_materials": ["PLA"], "loaded_material": "PLA"},
            {"printer_id": "p", "build_volume_mm": [200, 200, 200], "supported_materials": ["PLA"], "loaded_material": "PLA"}
        ],
        "job_requirements": {},
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Duplicate printer_id"):
        load_fleet_settings(path)
