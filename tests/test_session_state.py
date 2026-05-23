from utils.session_state import (
    DEFAULTS,
    FeatureFlags,
    SessionDefaults,
    SessionStateStore,
)



def test_defaults_are_available():
    assert isinstance(DEFAULTS, SessionDefaults)
    assert DEFAULTS.selected_currency == 'EUR'



def test_session_state_initialization():
    store = SessionStateStore()
    store.initialize_defaults()

    snapshot = store.snapshot()
    assert 'selected_currency' in snapshot
    assert snapshot['selected_currency'] == 'EUR'



def test_session_state_set_and_get():
    store = SessionStateStore()
    store.set('project', 'demo')

    assert store.get('project') == 'demo'



def test_feature_flags_reflect_state():
    store = SessionStateStore()
    store.set('diagnostics_enabled', True)

    flags = FeatureFlags(store)

    assert flags.diagnostics_enabled is True
