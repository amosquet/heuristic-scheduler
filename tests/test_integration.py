import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import load_job_data
from simulate import simulation

@pytest.mark.parametrize("filename", ["jobs.json", "jobs1.json", "jobs3.json"])
def test_simulation_with_real_data(filename):
    """Integration test: runs the simulation against the sample job files to ensure no crashes."""
    filepath = Path(__file__).resolve().parent.parent / filename
    
    # Only test if file exists (just in case they are removed)
    if not filepath.exists():
        pytest.skip(f"File {filename} not found.")
        
    jobs = load_job_data(filepath)
    assert len(jobs) > 0, f"No jobs loaded from {filename}"
    
    # Run the simulation
    execution_sequence = simulation(jobs, alpha=0.05, buffer_time=600)
    
    # Assert that all jobs were processed
    assert len(execution_sequence) == len(jobs)
    
    # Verify sequence constraints: each job should start after or at its submit time
    for record in execution_sequence:
        assert record["start_time"] >= record["submit_time"]
    
    # Verify sequence constraints: each job should start at or after the previous job's next_ready_time
    for i in range(1, len(execution_sequence)):
        assert execution_sequence[i]["start_time"] >= execution_sequence[i-1]["next_ready_time"]
