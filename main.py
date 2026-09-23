import argparse
from pathlib import Path

import data
from simulate import simulation


def main():
    parser = argparse.ArgumentParser(
        description="Run heuristic scheduler simulation on print jobs."
    )
    parser.add_argument(
        "filepath",
        nargs="?",
        default="jobs.json",
        help="Path to the JSON file containing print jobs (default: jobs.json)",
    )
    parser.add_argument(
        "--alpha",
        "-a",
        type=float,
        default=0.05,
        help="Aging coefficient for dynamic priority calculation (default: 0.05)",
    )
    parser.add_argument(
        "--buffer-time",
        "-b",
        type=int,
        default=600,
        help="Standard buffer time in seconds between prints for bed clearing (default: 600)",
    )

    args = parser.parse_args()

    if Path(args.filepath).exists():
        jobs = data.load_job_data(args.filepath)
    else:
        print(f"File '{args.filepath}' not found. Using built-in sample jobs.")
        jobs = [
            data.PrintJob(job_id=1, base_weight=50, submit_time=0, print_duration=1800),
            data.PrintJob(
                job_id=2, base_weight=80, submit_time=300, print_duration=3600
            ),
            data.PrintJob(
                job_id=3, base_weight=20, submit_time=600, print_duration=1200
            ),
        ]

    simulation(jobs, alpha=args.alpha, buffer_time=args.buffer_time)


if __name__ == "__main__":
    main()
