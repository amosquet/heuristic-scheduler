import sys
from pathlib import Path
import pytest
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import PrintJob, load_job_data

def test_printjob_calculate_weight():
    """Test dynamic weight calculation."""
    job = PrintJob(job_id=1, base_weight=50, submit_time=100, print_duration=3600)
    
    # At submit time, weight is base_weight
    assert job.calculate_weight(current_time=100, alpha=0.1) == 50.0
    
    # 100 seconds later, with alpha 0.1, weight should increase by 10
    assert job.calculate_weight(current_time=200, alpha=0.1) == 60.0
    
    # Negative time difference (current time before submit time)
    # Theoretically shouldn't happen in our queue, but testing the math
    assert job.calculate_weight(current_time=50, alpha=0.1) == 45.0

def test_load_job_data_list(tmp_path):
    """Test loading a standard list of jobs from JSON."""
    data = [
        {"job_id": 1, "base_weight": 50, "submit_time": 0, "print_duration": 1000},
        {"job_id": 2, "base_weight": 90, "submit_time": 300, "print_duration": 3600}
    ]
    file_path = tmp_path / "jobs.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
        
    jobs = load_job_data(file_path)
    assert len(jobs) == 2
    assert jobs[0].job_id == 1
    assert jobs[0].base_weight == 50
    assert jobs[1].job_id == 2
    assert jobs[1].print_duration == 3600

def test_load_job_data_dict(tmp_path):
    """Test loading jobs wrapped in a dictionary under a 'jobs' key."""
    data = {
        "jobs": [
            {"job_id": 1, "base_weight": 50, "submit_time": 0, "print_duration": 1000}
        ],
        "metadata": "something else"
    }
    file_path = tmp_path / "jobs_dict.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
        
    jobs = load_job_data(file_path)
    assert len(jobs) == 1
    assert jobs[0].job_id == 1

def test_load_job_data_empty_dict(tmp_path):
    """Test loading a dictionary without a 'jobs' key."""
    data = {"other_key": []}
    file_path = tmp_path / "empty_dict.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
        
    jobs = load_job_data(file_path)
    assert len(jobs) == 0

def test_load_job_data_missing_fields(tmp_path):
    """Test loading a job with missing fields raises TypeError."""
    data = [{"job_id": 1, "base_weight": 50}]  # Missing submit_time and print_duration
    file_path = tmp_path / "missing_fields.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
        
    with pytest.raises(TypeError):
        load_job_data(file_path)
