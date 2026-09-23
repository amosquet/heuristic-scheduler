import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrintJob:
    job_id: int
    base_weight: int
    submit_time: int
    print_duration: int
    cancelled: bool = False

    def calculate_weight(self, current_time: int, alpha: float) -> float:
        """Calculate dynamic priority weight based on waiting time and aging factor alpha."""
        return self.base_weight + alpha * (current_time - self.submit_time)


def load_job_data(filepath: str | Path) -> list[PrintJob]:
    """Load print jobs from a JSON file."""
    with open(filepath, "r") as file:
        data = json.load(file)

    raw_jobs = data if isinstance(data, list) else data.get("jobs", [])
    return [PrintJob(**job) for job in raw_jobs]
