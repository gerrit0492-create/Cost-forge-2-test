from pathlib import Path


EXPECTED_TERMS = [
    'price_eur_per_kg',
    'material_cost',
    'process_cost',
    'total_cost',
    'margin_pct',
]


SEARCH_FILES = [
    'utils/io.py',
    'utils/pricing.py',
]



def test_core_costing_terms_exist_in_engine_files():
    combined = ''
    for file in SEARCH_FILES:
        path = Path(file)
        assert path.exists(), f'Missing required file: {file}'
        combined += path.read_text(encoding='utf-8')

    missing = [term for term in EXPECTED_TERMS if term not in combined]
    assert missing == []
