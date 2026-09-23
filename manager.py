import heapq

from data import PrintJob


def static_score(job: PrintJob, alpha: float) -> float:
    """Calculate the time-invariant component of the priority score.

    Since dynamic_priority(t) = base_weight + alpha * (t - submit_time)
                              = (base_weight - alpha * submit_time) + alpha * t,
    the relative ranking across jobs with the same alpha at any time t is
    equivalent to ordering by static_score = base_weight - alpha * submit_time.
    """
    if isinstance(job, PrintJob):
        return job.base_weight - (alpha * job.submit_time)
    raise TypeError("Expected a PrintJob instance")


def dynamic_score(job: PrintJob, current_time: int, alpha: float) -> float:
    """Calculate the dynamic priority score at a specific current_time."""
    return job.calculate_weight(current_time, alpha)


def scorer(
    jobs: list[PrintJob] | PrintJob, alpha: float, queue: list | None = None
) -> list:
    """Scores incoming print jobs and pushes them into the priority queue."""
    if queue is None:
        queue = []

    if isinstance(jobs, list):
        for job in jobs:
            score = static_score(job, alpha)
            # Max-heap emulation using negative score. Tie-breakers: submit_time, then job_id
            heapq.heappush(queue, (-score, job.submit_time, job.job_id, job))
        return queue
    else:
        job = jobs
        score = static_score(job, alpha)
        heapq.heappush(queue, (-score, job.submit_time, job.job_id, job))
        return queue


def dispatch_job(queue: list) -> PrintJob | None:
    """Pops and returns the highest priority job from the queue."""
    while queue:
        *_, job = heapq.heappop(queue)
        if not getattr(job, "cancelled", False):
            return job
    return None
