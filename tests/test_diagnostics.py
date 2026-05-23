from utils.diagnostics import environment_status, file_status, health_summary, module_status



def test_environment_status_contains_python():
    env = environment_status()
    assert 'python' in env
    assert env['python']



def test_health_summary_structure():
    summary = health_summary()
    assert 'files_ok' in summary
    assert 'modules_ok' in summary
    assert 'environment' in summary



def test_file_status_contains_home_py():
    rows = file_status()
    paths = [row['path'] for row in rows]
    assert 'home.py' in paths



def test_module_status_has_streamlit_entry():
    rows = module_status()
    modules = [row['module'] for row in rows]
    assert 'streamlit' in modules
