import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulate import simulation
from data import PrintJob

def test_simulation_empty_list():
    """Test simulation with no jobs."""
    result = simulation([], alpha=0.05, buffer_time=600)
    assert result == []

def test_simulation_basic_ordering():
    """Test that jobs submitted at the same time are ordered by base weight then ID."""
    jobs = [
        PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000),
        PrintJob(job_id=2, base_weight=50, submit_time=0, print_duration=1000),
        PrintJob(job_id=3, base_weight=50, submit_time=0, print_duration=1000),
    ]
    result = simulation(jobs, alpha=0.05, buffer_time=600)
    
    assert len(result) == 3
    # Job 2 should go first (highest weight, lower ID than 3)
    assert result[0]["job_id"] == 2
    # Job 3 should go second (highest weight, higher ID than 2)
    assert result[1]["job_id"] == 3
    # Job 1 goes last (lowest weight)
    assert result[2]["job_id"] == 1

def test_simulation_with_buffer_time():
    """Test that buffer time is correctly applied to start times and next_ready_time."""
    jobs = [
        PrintJob(job_id=1, base_weight=50, submit_time=0, print_duration=1000),
        PrintJob(job_id=2, base_weight=50, submit_time=0, print_duration=1000),
    ]
    buffer_time = 300
    result = simulation(jobs, alpha=0.05, buffer_time=buffer_time)
    
    # First job starts at 0, finishes at 1000
    assert result[0]["start_time"] == 0
    assert result[0]["finish_time"] == 1000
    assert result[0]["next_ready_time"] == 1300
    
    # Second job starts at 1300 (after buffer time)
    assert result[1]["start_time"] == 1300
    assert result[1]["finish_time"] == 2300
    assert result[1]["next_ready_time"] == 2600

def test_simulation_dynamic_priority():
    """Test that dynamic priority correctly re-orders jobs arriving at different times."""
    # A job with low weight that has waited a long time
    job_old = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    # A job with high weight that arrives right when the bed is available
    job_new = PrintJob(job_id=2, base_weight=50, submit_time=1000, print_duration=1000)
    
    # Another job to occupy the printer so job_old has to wait
    job_blocker = PrintJob(job_id=3, base_weight=100, submit_time=0, print_duration=1000)
    
    # At T=0, job_blocker (100) and job_old (10) are in queue. Blocker wins.
    # Blocker finishes at T=1000. Next ready is 1000 + 0 buffer = 1000.
    # At T=1000, job_new arrives. 
    # Job old weight: 10 + 0.05 * (1000 - 0) = 60
    # Job new weight: 50 + 0.05 * (1000 - 1000) = 50
    # Job old should beat job new.
    
    jobs = [job_old, job_new, job_blocker]
    result = simulation(jobs, alpha=0.05, buffer_time=0)
    
    assert result[0]["job_id"] == 3
    assert result[1]["job_id"] == 1
    assert result[2]["job_id"] == 2

def test_simulation_cancellation():
    """Test that cancelled jobs are skipped during simulation."""
    job_valid = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    job_cancelled = PrintJob(job_id=2, base_weight=100, submit_time=0, print_duration=1000, cancelled=True)
    
    jobs = [job_valid, job_cancelled]
    result = simulation(jobs, alpha=0.05, buffer_time=600)
    
    assert len(result) == 1
    assert result[0]["job_id"] == 1

def test_simulation_all_queued_jobs_cancelled():
    """Test that simulation handles when all jobs in pending queue are cancelled."""
    job1 = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=1000)
    job2 = PrintJob(job_id=2, base_weight=100, submit_time=50, print_duration=1000, cancelled=True)
    job3 = PrintJob(job_id=3, base_weight=100, submit_time=50, print_duration=1000, cancelled=True)
    
    # job1 arrives at T=0. It starts.
    # At T=50, job2 and job3 arrive but they are cancelled.
    # While job1 is printing, job2 and job3 are queued but cancelled.
    # After job1 finishes, simulation will pull from queue and dispatch_job returns None.
    # This hits the `if dispatched_job is None: break` logic if there are no remaining jobs,
    # or the loop handles it.
    
    jobs = [job1, job2, job3]
    result = simulation(jobs, alpha=0.05, buffer_time=600)
    
    assert len(result) == 1
    assert result[0]["job_id"] == 1

def test_simulation_gap_in_jobs():
    """Test simulation jumping forward in time when queue is empty but jobs remain."""
    job1 = PrintJob(job_id=1, base_weight=10, submit_time=0, print_duration=100)
    # job1 starts at 0, finishes at 100, next ready at 100+600=700
    # Queue is empty. Next job doesn't arrive until T=2000.
    job2 = PrintJob(job_id=2, base_weight=10, submit_time=2000, print_duration=100)
    
    jobs = [job1, job2]
    result = simulation(jobs, alpha=0.05, buffer_time=600)
    
    assert len(result) == 2
    assert result[0]["job_id"] == 1
    assert result[1]["job_id"] == 2
    assert result[1]["start_time"] == 2000
