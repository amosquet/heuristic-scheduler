import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from manager import static_score

def test_static_score_invalid_type():
    """Validates that static_score raises TypeError if not given a PrintJob."""
    with pytest.raises(TypeError, match="Expected a PrintJob instance"):
        static_score("Not a print job", 0.05)

def test_dynamic_score_wrapper():
    from data import PrintJob
    from manager import dynamic_score
    job = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    assert dynamic_score(job, current_time=100, alpha=0.1) == 20.0

def test_scorer_single_job():
    from data import PrintJob
    from manager import scorer
    job = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    queue = []
    scorer(job, alpha=0.1, queue=queue)
    assert len(queue) == 1
    # Priority queue stores (-score, submit_time, job_id, job)
    assert queue[0][0] == -10  # Score is 10, so stored as -10
    assert queue[0][3] == job

def test_scorer_no_queue():
    from data import PrintJob
    from manager import scorer
    job = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    queue = scorer(job, alpha=0.1)
    assert len(queue) == 1
    assert queue[0][3] == job

def test_scorer_empty_list():
    from manager import scorer
    queue = []
    scorer([], alpha=0.1, queue=queue)
    assert len(queue) == 0

def test_dispatch_empty_queue():
    from manager import dispatch_job
    queue = []
    assert dispatch_job(queue) is None

def test_dispatch_all_cancelled():
    from data import PrintJob
    from manager import scorer, dispatch_job
    job1 = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000, cancelled=True)
    job2 = PrintJob(job_id=2, base_weight=20, submit_time=0, print_duration=1000, cancelled=True)
    queue = []
    scorer([job1, job2], alpha=0.1, queue=queue)
    assert dispatch_job(queue) is None

def test_tie_breakers():
    from data import PrintJob
    from manager import scorer, dispatch_job
    # Jobs with identical static scores (base_weight - alpha*submit_time)
    job1 = PrintJob(job_id=2, base_weight=10, submit_time=0, print_duration=1000)
    job2 = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    queue = []
    scorer([job1, job2], alpha=0.1, queue=queue)
    # Tie broken by submit_time (equal), then job_id (job2 has lower job_id so should be popped first)
    first_job = dispatch_job(queue)
    assert first_job.job_id == 1
    second_job = dispatch_job(queue)
    assert second_job.job_id == 2
