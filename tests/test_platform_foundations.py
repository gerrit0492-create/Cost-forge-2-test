from utils.api_contracts import as_dict, failure, success
from utils.cache_diagnostics import SimpleCacheDiagnostics
from utils.event_bus import EventBus
from utils.plugins import PluginDefinition, PluginRegistry



def test_api_contract_success():
    result = success({'ok': True})
    payload = as_dict(result)

    assert payload['ok'] is True



def test_plugin_registry_register_and_get():
    registry = PluginRegistry()

    plugin = PluginDefinition(
        name='demo',
        version='1.0',
        handler=lambda: None,
    )

    registry.register(plugin)

    assert registry.get('demo') is not None



def test_event_bus_publish_subscribe():
    bus = EventBus()

    received = []

    bus.subscribe('pricing', lambda payload: received.append(payload))
    bus.publish('pricing', {'value': 123})

    assert received[0]['value'] == 123



def test_cache_diagnostics_hit_and_miss():
    cache = SimpleCacheDiagnostics()

    value1, metric1 = cache.get_or_compute('x', lambda: 42)
    value2, metric2 = cache.get_or_compute('x', lambda: 99)

    assert value1 == 42
    assert value2 == 42
    assert metric1.hit is False
    assert metric2.hit is True
