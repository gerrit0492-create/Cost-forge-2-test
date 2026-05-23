from utils.config import AppConfig, get_config
from utils.logging_utils import get_logger



def test_get_config_returns_app_config():
    config = get_config()
    assert isinstance(config, AppConfig)



def test_config_contains_expected_fields():
    config = get_config()
    assert config.app_name
    assert config.environment
    assert config.repo_root.exists()



def test_logger_creation():
    logger = get_logger('cost_forge_test')
    logger.info('logger smoke test')
    assert logger.name == 'cost_forge_test'
