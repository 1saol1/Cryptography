from src.core.config import ConfigManager


def test_config_loading():
    config = ConfigManager("src/database/cryptosafe.db")

    assert config is not None