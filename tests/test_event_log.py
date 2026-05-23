from utils.event_log import (
    EventRecord,
    create_event,
    event_to_dict,
    event_to_log_line,
)



def test_create_event_returns_record():
    event = create_event(
        event_type='import',
        source='bom_loader',
        message='BOM imported',
        metadata={'rows': 100},
    )

    assert isinstance(event, EventRecord)
    assert event.event_type == 'import'



def test_event_to_dict_contains_expected_keys():
    event = create_event('test', 'unit', 'hello')
    payload = event_to_dict(event)

    assert 'timestamp_utc' in payload
    assert payload['event_type'] == 'test'



def test_event_to_log_line_contains_message():
    event = create_event('warning', 'pricing', 'negative value detected')
    line = event_to_log_line(event)

    assert 'negative value detected' in line
