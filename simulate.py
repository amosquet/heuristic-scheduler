import manager
from data import PrintJob


def simulation(
    master_job_list: list[PrintJob], alpha: float, buffer_time: int = 600
) -> list[dict]:
    """Orchestrates the heuristic scheduling simulation.

    Args:
        master_job_list: List of PrintJob instances to schedule.
        alpha: Aging coefficient for dynamic priority calculation.
        buffer_time: Standard buffer in seconds between prints for bed clearing (default: 600s).

    Returns:
        List of dictionaries detailing the execution record of each dispatched job.
    """
    if not master_job_list:
        print("No jobs to simulate.")
        return []

    # Sort remaining master jobs chronologically by submit time
    remaining_jobs = sorted(master_job_list, key=lambda j: (j.submit_time, j.job_id))

    current_time = 0
    pending_queue: list = []
    execution_sequence: list[dict] = []
    step = 1

    header_info = f"Alpha (Aging Rate): {alpha} | Bed Clear Buffer: {buffer_time}s | Total Jobs: {len(master_job_list)}"
    print("=" * 105)
    print(f"{'HEURISTIC PRINT SCHEDULER SIMULATION':^105}")
    print(f"{header_info:^105}")
    print("=" * 105)
    print(
        f"{'Seq':<4} | {'Job ID':<7} | {'Submit (s)':<10} | {'Start (s)':<10} | "
        f"{'Wait (s)':<9} | {'Duration (s)':<12} | {'Finish (s)':<10} | {'Next Ready (s)':<14} | {'Priority':<10}"
    )
    print("-" * 105)

    while remaining_jobs or pending_queue:
        # 1. Scan master_job_list for jobs where submit_time <= current_time and transfer into pending_queue
        arrived_jobs = []
        unprocessed = []
        for job in remaining_jobs:
            if job.submit_time <= current_time:
                arrived_jobs.append(job)
            else:
                unprocessed.append(job)
        remaining_jobs = unprocessed

        # 2. Execute queue management logic to score and enqueue newly arrived jobs
        if arrived_jobs:
            manager.scorer(arrived_jobs, alpha, pending_queue)

        # If queue is empty but future jobs remain, advance current_time to next arrival
        if not pending_queue and remaining_jobs:
            current_time = remaining_jobs[0].submit_time
            continue

        # 3. Execute dispatch_job() to select the winning print
        dispatched_job = manager.dispatch_job(pending_queue)
        if dispatched_job is None:
            break

        start_time = current_time
        wait_time = start_time - dispatched_job.submit_time
        dynamic_weight = dispatched_job.calculate_weight(current_time, alpha)
        finish_time = start_time + dispatched_job.print_duration
        next_available_time = finish_time + buffer_time

        record = {
            "sequence": step,
            "job_id": dispatched_job.job_id,
            "base_weight": dispatched_job.base_weight,
            "submit_time": dispatched_job.submit_time,
            "start_time": start_time,
            "wait_time": wait_time,
            "print_duration": dispatched_job.print_duration,
            "finish_time": finish_time,
            "next_ready_time": next_available_time,
            "dynamic_priority": dynamic_weight,
            "job": dispatched_job,
        }
        execution_sequence.append(record)

        # 5. Print the execution sequence step to terminal
        print(
            f"{step:<4} | {dispatched_job.job_id:<7} | {dispatched_job.submit_time:<10} | "
            f"{start_time:<10} | {wait_time:<9} | {dispatched_job.print_duration:<12} | "
            f"{finish_time:<10} | {next_available_time:<14} | {dynamic_weight:<10.2f}"
        )

        # 4. Advance current_time by print_duration plus bed clearing buffer
        current_time = next_available_time
        step += 1

    # Print summary statistics
    total_wait = sum(r["wait_time"] for r in execution_sequence)
    avg_wait = total_wait / len(execution_sequence) if execution_sequence else 0
    total_print_time = sum(r["print_duration"] for r in execution_sequence)
    makespan = execution_sequence[-1]["finish_time"] if execution_sequence else 0
    execution_order_str = " -> ".join(f"Job #{r['job_id']}" for r in execution_sequence)

    print("=" * 105)
    print(f"{'SIMULATION SUMMARY':^105}")
    print("-" * 105)
    print(f"  • Total Jobs Processed : {len(execution_sequence)}")
    print(f"  • Execution Order      : {execution_order_str}")
    print(f"  • Final Job Completion : {makespan} s")
    print(f"  • Total Print Duration : {total_print_time} s")
    print(f"  • Average Wait Time    : {avg_wait:.2f} s")
    print(f"  • Total Simulation End : {current_time} s (including final buffer)")
    print("=" * 105 + "\n")

    return execution_sequence
