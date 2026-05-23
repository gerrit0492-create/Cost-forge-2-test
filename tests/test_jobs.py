from utils.jobs import (
    InMemoryJobRegistry,
    JobStatus,
    create_job,
    run_job,
)



def test_create_job_generates_pending_job():
    job = create_job('import_bom')

    assert job.name == 'import_bom'
    assert job.status == JobStatus.PENDING



def test_run_job_success():
    job = create_job('math')

    result = run_job(job, lambda a, b: a + b, 2, 3)

    assert result.status == JobStatus.SUCCEEDED
    assert result.result == 5



def test_run_job_failure():
    job = create_job('failure')

    def explode():
        raise ValueError('boom')

    result = run_job(job, explode)

    assert result.status == JobStatus.FAILED
    assert 'ValueError' in result.error



def test_job_registry_add_and_get():
    registry = InMemoryJobRegistry()

    job = create_job('registry_test')
    registry.add(job)

    loaded = registry.get(job.job_id)

    assert loaded is not None
    assert loaded.job_id == job.job_id
