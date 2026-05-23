import ast
from pathlib import Path


HOME = Path('home.py')


def _parse_home():
    return ast.parse(HOME.read_text(encoding='utf-8'))


def _page_registry_dict():
    tree = _parse_home()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '_P':
                    assert isinstance(node.value, ast.Dict), '_P must be a dictionary'
                    return node.value
    raise AssertionError('home.py must define _P page registry')


def test_page_registry_has_no_duplicate_literal_keys():
    registry = _page_registry_dict()
    keys = [key.value for key in registry.keys if isinstance(key, ast.Constant)]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    assert duplicates == []


def test_registered_streamlit_page_files_exist():
    registry = _page_registry_dict()
    missing = []
    for value in registry.values:
        if not isinstance(value, ast.Call):
            continue
        if not value.args:
            continue
        first_arg = value.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            if not Path(first_arg.value).exists():
                missing.append(first_arg.value)
    assert missing == []


def test_critical_pages_are_registered():
    registry = _page_registry_dict()
    home_source = HOME.read_text(encoding='utf-8')
    required_paths = [
        'pages/45_Command_Centre.py',
        'pages/47_Carbon_Energy.py',
        'pages/48_Stakeholder_Package.py',
        'pages/51_QMS_Prices.py',
    ]
    for path in required_paths:
        assert path in home_source
