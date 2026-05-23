from pathlib import Path


REQUIRED_PAGES = [
    'pages/45_Command_Centre.py',
    'pages/47_Carbon_Energy.py',
    'pages/48_Stakeholder_Package.py',
    'pages/51_QMS_Prices.py',
]


def test_critical_pages_exist():
    missing = [p for p in REQUIRED_PAGES if not Path(p).exists()]
    assert missing == []



def test_home_file_exists():
    assert Path('home.py').exists()



def test_requirements_exists():
    assert Path('requirements.txt').exists()
