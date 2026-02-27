from src.core.config import ConfigManager


def test_config_loading():
    config = ConfigManager("src/database/cryptosafe.db")

    # проверяем что объект создаётся
    assert config is not None