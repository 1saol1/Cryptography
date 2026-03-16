import unittest
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.core.crypto.key_manager import KeyManager


class TestKeyConsistency(unittest.TestCase):

    def setUp(self):
        self.key_manager = KeyManager()
        self.test_password = "TestPassword123!@#"
        self.test_salt = b"fixed_test_salt_16b"

    def test_derive_key_100_times(self):
        first_key = self.key_manager.derive_encryption_key(self.test_password, self.test_salt)

        for i in range(99):
            current_key = self.key_manager.derive_encryption_key(self.test_password, self.test_salt)
            if current_key != first_key:
                self.fail("Ключ отличается от первого")


if __name__ == "__main__":
    unittest.main()