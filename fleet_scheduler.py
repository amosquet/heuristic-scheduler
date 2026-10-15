from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence

from data import PrintJob, load_job_data


@dataclass(frozen=True)
class Printer:
    printer_id: str
    build_volume_mm: tuple[float, float, float]
    supported_materials: frozenset[str]
    loaded_material: str
    online: bool = True
    available_at: int = 0


@dataclass(frozen=True)
class Requirements:
    material: str
    dimensions_mm: tuple[float, float, float]


def _nonnegative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer (seconds)")
    return value


def _dimensions(value: object, field: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field} must contain exactly three dimensions in mm")
    dimensions = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise ValueError(f"{field} must contain numbers")
        number = float(component)
        if not isfinite(number) or number <= 0:
            raise ValueError(f"{field} must contain positive, finite dimensions")
        dimensions.append(number)
    return tuple(dimensions)


def _material(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty material name")
    return value.strip().upper()


def _read_printer(raw: dict) -> Printer:
    if not isinstance(raw, dict):
        raise ValueError("Each printer must be an object")
    printer_id = raw.get("printer_id")
    if not isinstance(printer_id, str) or not printer_id.strip():
        raise ValueError("Every printer needs a non-empty printer_id")
    materials = raw.get("supported_materials")
    if not isinstance(materials, list) or not materials:
        raise ValueError(f"{printer_id}: supported_materials must be a non-empty list")
    supported = frozenset(_material(m, "supported_materials entry") for m in materials)
    loaded = _material(raw.get("loaded_material"), f"{printer_id}.loaded_material")
    if loaded not in supported:
        raise ValueError(f"{printer_id}: loaded material must be supported")
    online = raw.get("online", True)
    if type(online) is not bool:
        raise ValueError(f"{printer_id}: online must be true or false")
    return Printer(
        printer_id=printer_id.strip(),
        build_volume_mm=_dimensions(raw.get("build_volume_mm"), f"{printer_id}.build_volume_mm"),
        supported_materials=supported,
        loaded_material=loaded,
        online=online,
        available_at=_nonnegative_int(raw.get("available_at", 0), f"{printer_id}.available_at"),
    )


def _read_requirements(raw: dict, job_id: str) -> Requirements:
    if not isinstance(raw, dict):
        raise ValueError(f"Missing requirements object for job {job_id}")
    return Requirements(
        material=_material(raw.get("material"), f"job {job_id}.material"),
        dimensions_mm=_dimensions(raw.get("dimensions_mm"), f"job {job_id}.dimensions_mm"),
    )


def load_fleet_settings(path: str | Path) -> tuple[list[Printer], dict[str, Requirements]]:
    with Path(path).open(encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError("Fleet configuration must be a JSON object")
    raw_printers = config.get("printers")
    if not isinstance(raw_printers, list):
        raise ValueError("Fleet configuration needs a printers list")
    printers = [_read_printer(value) for value in raw_printers]
    ids = [p.printer_id for p in printers]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate printer_id in fleet configuration")
    raw_requirements = config.get("job_requirements")
    if not isinstance(raw_requirements, dict):
        raise ValueError("Fleet configuration needs a job_requirements object")
    requirements = {
        str(job_id): _read_requirements(value, str(job_id))
        for job_id, value in raw_requirements.items()
    }
    return printers, requirements


def fits(printer: Printer, requirement: Requirements) -> bool:
    return all(
        required <= available
        for required, available in zip(requirement.dimensions_mm, printer.build_volume_mm)
    )


def compatible(printer: Printer, requirement: Requirements) -> bool:
    return (
        printer.online
        and requirement.material in printer.supported_materials
        and requirement.material == printer.loaded_material
        and fits(printer, requirement)
    )


def _block_reason(requirement: Requirements, printers: Sequence[Printer]) -> str:
    online = [p for p in printers if p.online]
    if not online:
        return "no_online_printers"
    if not any(requirement.material in p.supported_materials for p in online):
        return "material_unsupported"
    if not any(p.loaded_material == requirement.material for p in online):
        return "material_not_loaded"
    return "exceeds_build_volume"


def _validate_jobs(jobs: Sequence[PrintJob], requirements: Mapping[str, Requirements]) -> None:
    seen: set[str] = set()
    for job in jobs:
        key = str(job.job_id)
        if key in seen:
            raise ValueError(f"Duplicate job_id {key}")
        seen.add(key)
        _nonnegative_int(job.submit_time, f"job {key}.submit_time")
        if type(job.print_duration) is not int or job.print_duration <= 0:
            raise ValueError(f"job {key}.print_duration must be a positive integer")
        if not isinstance(job.base_weight, (int, float)) or isinstance(job.base_weight, bool) or not isfinite(job.base_weight):
            raise ValueError(f"job {key}.base_weight must be finite")
        if type(job.cancelled) is not bool:
            raise ValueError(f"job {key}.cancelled must be true or false")
        if not job.cancelled and key not in requirements:
            raise ValueError(f"Missing sliced material/dimensions for job {key}")


def plan_fleet(
    jobs: Sequence[PrintJob],
    printers: Sequence[Printer],
    requirements: Mapping[str, Requirements],
    *,
    alpha: float = 0.05,
    buffer_time: int = 600,
    now: int = 0,
) -> dict:
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be a finite non-negative number")
    _nonnegative_int(now, "now")
    _nonnegative_int(buffer_time, "buffer_time")
    _validate_jobs(jobs, requirements)

    printer_ids = [p.printer_id for p in printers]
    if len(set(printer_ids)) != len(printer_ids):
        raise ValueError("Duplicate printer_id")
    free_at = {p.printer_id: max(now, p.available_at) for p in printers}
    active = [p for p in printers if p.online]
    pending: dict[str, PrintJob] = {}
    blocked = []

    for job in jobs:
        key = str(job.job_id)
        if job.cancelled:
            blocked.append({"job_id": job.job_id, "reason": "cancelled"})
            continue
        specs = requirements[key]
        if not any(compatible(p, specs) for p in active):
            blocked.append({"job_id": job.job_id, "reason": _block_reason(specs, printers)})
            continue
        pending[key] = job

    timeline: list[dict] = []
    clock = now
    while pending:
        available = [p for p in active if free_at[p.printer_id] <= clock]
        arrived = [job for job in pending.values() if job.submit_time <= clock]
        matches = [
            job for job in arrived
            if any(compatible(p, requirements[str(job.job_id)]) for p in available)
        ]

        if not matches:
            future = [j.submit_time for j in pending.values() if j.submit_time > clock]
            future += [free_at[p.printer_id] for p in active if free_at[p.printer_id] > clock]
            if not future:
                raise RuntimeError("Pending jobs could not be assigned despite passing compatibility checks")
            clock = min(future)
            continue

        def priority_key(job: PrintJob) -> tuple:
            allowed_count = sum(compatible(p, requirements[str(job.job_id)]) for p in active)
            return (-job.calculate_weight(clock, alpha), allowed_count, job.submit_time, str(job.job_id))

        job = min(matches, key=priority_key)
        requirement = requirements[str(job.job_id)]
        choices = [p for p in available if compatible(p, requirement)]

        def printer_key(printer: Printer) -> tuple:
            sole_use_count = sum(
                1 for other in arrived
                if other.job_id != job.job_id
                and [p.printer_id for p in active if compatible(p, requirements[str(other.job_id)])] == [printer.printer_id]
            )
            build_volume = printer.build_volume_mm[0] * printer.build_volume_mm[1] * printer.build_volume_mm[2]
            return (sole_use_count, build_volume, printer.printer_id)

        printer = min(choices, key=printer_key)
        start = clock
        finish = start + job.print_duration
        next_ready = finish + buffer_time
        timeline.append({
            "job_id": job.job_id,
            "printer_id": printer.printer_id,
            "material": requirement.material,
            "start_time": start,
            "finish_time": finish,
            "next_ready_time": next_ready,
            "wait_time": start - job.submit_time,
            "priority_at_dispatch": job.calculate_weight(clock, alpha),
        })
        free_at[printer.printer_id] = next_ready
        del pending[str(job.job_id)]

    timeline.sort(key=lambda row: (row["start_time"], row["printer_id"], str(row["job_id"])))
    return {
        "assignments": timeline,
        "unassigned": blocked,
        "summary": {
            "jobs_assigned": len(timeline),
            "jobs_unassigned": len(blocked),
            "last_finish_time": max((row["finish_time"] for row in timeline), default=now),
            "average_wait_s": sum(row["wait_time"] for row in timeline) / len(timeline) if timeline else 0.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PrintHive printer-aware scheduling demonstration")
    parser.add_argument("jobs", help="Existing scheduler jobs JSON")
    parser.add_argument("fleet", help="Printer inventory and sliced job metadata JSON")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--buffer-time", type=int, default=600)
    parser.add_argument("--now", type=int, default=0, help="Current simulation time in seconds")
    parser.add_argument("--out", default="", help="Optional output path for API-friendly JSON")
    arguments = parser.parse_args()
    try:
        jobs = load_job_data(arguments.jobs)
        printers, requirements = load_fleet_settings(arguments.fleet)
        plan = plan_fleet(jobs, printers, requirements, alpha=arguments.alpha, buffer_time=arguments.buffer_time, now=arguments.now)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))

    print("PRINTHIVE — PROPOSED PRINTER ASSIGNMENTS")
    print(f"{'Job':<10}{'Printer':<20}{'Material':<10}{'Start(s)':>10}{'Finish(s)':>12}{'Wait(s)':>10}")
    print("-" * 73)
    for row in plan["assignments"]:
        print(f"{str(row['job_id']):<10}{row['printer_id']:<20}{row['material']:<10}{row['start_time']:>10}{row['finish_time']:>12}{row['wait_time']:>10}")
    if plan["unassigned"]:
        print("\nREQUIRES ATTENTION (not assigned to a printer)")
        for row in plan["unassigned"]:
            print(f"  job {row['job_id']}: {row['reason']}")
    if arguments.out:
        path = Path(arguments.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"\nJSON schedule written to {path}")


if __name__ == "__main__":
    main()