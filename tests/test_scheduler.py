import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import manager
from data import PrintJob


def test_dynamic_insertion_and_removal():
    """Validates that the queue handles mid-execution additions and cancellations."""
    queue = []
    alpha = 0.05

    # Event 1: Initial state at T=0
    job_101 = PrintJob(job_id=101, base_weight=10, submit_time=0, print_duration=3600)
    job_102 = PrintJob(job_id=102, base_weight=50, submit_time=0, print_duration=7200)
    manager.scorer([job_101, job_102], alpha, queue)

    # Event 2: Job 102 is cancelled by a user at T=1000
    job_102.cancelled = True

    # Event 3: A high-priority staff print arrives dynamically at T=1500
    job_103 = PrintJob(
        job_id=103, base_weight=100, submit_time=1500, print_duration=1800
    )
    manager.scorer(job_103, alpha, queue)

    # Event 4: A standard student print arrives at T=1500
    job_104 = PrintJob(
        job_id=104, base_weight=10, submit_time=1500, print_duration=3600
    )
    manager.scorer(job_104, alpha, queue)

    # Verification Phase: Dispatching at T=1500
    # Expected Queue State:
    # - 102 should be silently discarded (cancelled).
    # - 103 Static Score: 100 - (0.05 * 1500) = 25
    # - 101 Static Score: 10 - (0.05 * 0) = 10
    # - 104 Static Score: 10 - (0.05 * 1500) = -65

    first_dispatch = manager.dispatch_job(queue)
    assert first_dispatch is not None
    assert first_dispatch.job_id == 103, (
        "Failed: High priority late arrival did not jump the queue."
    )

    second_dispatch = manager.dispatch_job(queue)
    assert second_dispatch is not None
    assert second_dispatch.job_id == 101, (
        "Failed: Cancelled job was dispatched or older job lost priority."
    )

    third_dispatch = manager.dispatch_job(queue)
    assert third_dispatch is not None
    assert third_dispatch.job_id == 104, (
        "Failed: Lowest priority job dispatched out of order."
    )

    empty_dispatch = manager.dispatch_job(queue)
    assert empty_dispatch is None, "Failed: Queue should be empty."


def test_priority_inversion_over_time():
    """Validates that a low-priority job mathematically overtakes a medium-priority job over time."""
    queue = []
    alpha = 0.05

    # Job A: Base weight 10, submitted at T=0
    job_a = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=3600)
    # Job B: Base weight 50, submitted at T=1000
    job_b = PrintJob(job_id=2, base_weight=50, submit_time=1000, print_duration=3600)

    manager.scorer([job_a, job_b], alpha, queue)

    # Static Score A: 10 - (0.05 * 0) = 10
    # Static Score B: 50 - (0.05 * 1000) = 0
    # Job A should have a higher mathematical score despite the lower base weight,
    # proving the linear aging modifier works correctly.

    first_dispatch = manager.dispatch_job(queue)
    assert first_dispatch.job_id == 1, (
        "Failed: Linear aging coefficient did not elevate older job priority."
    )
