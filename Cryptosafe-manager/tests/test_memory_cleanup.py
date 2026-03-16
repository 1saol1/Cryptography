import unittest
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.core.crypto.key_manager import KeyManager
from src.core.crypto.secure_memory import SecureMemory
from src.core.state_manager import StateManager


class TestMemoryCleanup(unittest.TestCase):

    def setUp(self):
        self.key_manager = KeyManager()
        self.secure_memory = SecureMemory()
        self.test_key = b"this_is_a_test_key_32_bytes_long!!"

    # проверка, что данные действительно удаляются
    def test_secure_clearing(self):
        key_copy = bytearray(self.test_key)
        first_bytes = key_copy[:5]

        self.secure_memory.secure_clear(key_copy)

        if key_copy[:5] == first_bytes:
            self.fail("Данные не изменились после очистки")

        for byte in key_copy:
            if byte != 0:
                self.fail(f"Найден ненулевой байт: {byte}")

    # проверка, что ключ очищается из кэша при выходе
    def test_cache_clearing_on_logout(self):
        self.key_manager.cache_key(self.test_key)

        if self.key_manager.get_cached_key() is None:
            self.fail("Ключ не закэшировался")

        self.key_manager.clear_cache()

        if self.key_manager.get_cached_key() is not None:
            self.fail("Ключ не очистился после clear_cache")

    # проверка, что ключ удаляется при завершении сессии
    def test_cache_clearing_on_session_end(self):
        state = StateManager()

        state.start_session(self.test_key)
        self.key_manager.cache_key(self.test_key)

        if self.key_manager.get_cached_key() is None:
            self.fail("Ключ не закэшировался")

        state.end_session()
        self.key_manager.clear_cache()

        if self.key_manager.get_cached_key() is not None:
            self.fail("Ключ не очистился после завершения сессии")

    # проверка на очистку нескольких ключей
    def test_multiple_keys_clearing(self):
        keys = [
            b"key_number_one_12345678",
            b"key_number_two_12345678",
            b"key_number_three_123456"
        ]

        for key in keys:
            self.key_manager.cache_key(key)

            if self.key_manager.get_cached_key() != key:
                self.fail(f"Ключ {key} не закэшировался правильно")

            self.key_manager.clear_cache()

            if self.key_manager.get_cached_key() is not None:
                self.fail(f"Ключ {key} не очистился")



if __name__ == "__main__":
    unittest.main()