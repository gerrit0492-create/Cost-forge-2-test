from utils.runtime_health import (
    RuntimeHealthSnapshot,
    capture_runtime_health,
    runtime_health_as_dict,
)



def test_capture_runtime_health_returns_snapshot():
    snapshot = capture_runtime_health()

    assert isinstance(snapshot, RuntimeHealthSnapshot)
    assert snapshot.health
    assert snapshot.timing.elapsed_ms >= 0



def test_runtime_health_as_dict_contains_expected_keys():
    snapshot = capture_runtime_health()
    payload = runtime_health_as_dict(snapshot)

    assert 'timestamp_utc' in payload
    assert 'health' in payload
    assert 'timing' in payload
