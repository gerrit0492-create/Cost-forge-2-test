from utils.performance import TimingResult, measure_call, timer



def test_timer_context_manager_returns_timing_result():
    with timer('smoke') as bucket:
        x = sum(range(100))
        assert x > 0

    assert len(bucket) == 1
    assert isinstance(bucket[0], TimingResult)
    assert bucket[0].elapsed_ms >= 0



def test_measure_call_returns_result_and_timing():
    result, timing = measure_call('add', lambda a, b: a + b, 2, 3)

    assert result == 5
    assert isinstance(timing, TimingResult)
    assert timing.elapsed_ms >= 0
