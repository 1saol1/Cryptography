import unittest
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.core.crypto.placeholder import XORPlaceholderEncryption
from src.core.crypto.key_manager import KeyManager
from src.core.crypto.key_derivation import KeyDerivation
from src.core.crypto.authentication import AuthenticationService


class TestCryptoBasic(unittest.TestCase):

    def setUp(self):
        self.key_manager = KeyManager()
        self.crypto = XORPlaceholderEncryption(self.key_manager)

    def test_xor_encrypt_decrypt(self):
        salt = b"testsalt"
        key = self.key_manager.derive_encryption_key("password123", salt)
        data = b"secret data"

        encrypted = self.crypto.encrypt(data, key)
        decrypted = self.crypto.decrypt(encrypted, key)

        self.assertEqual(decrypted, data)


class TestArgon2Validation(unittest.TestCase):

    def setUp(self):
        self.test_password = "TestPassword123!@#"

    def test_default_parameters(self):
        derivation = KeyDerivation()
        auth_hash = derivation.create_auth_hash(self.test_password)

        self.assertIsNotNone(auth_hash)
        self.assertGreater(len(auth_hash), 0)
        self.assertIn("$argon2id$", auth_hash)

        result = derivation.verify_password(self.test_password, auth_hash)
        self.assertTrue(result)

    def test_different_time_cost(self):
        time_costs = [2, 3, 4]

        for time_cost in time_costs:
            derivation = KeyDerivation({
                'argon2_time': time_cost,
                'argon2_memory': 65536,
                'argon2_parallelism': 4
            })

            auth_hash = derivation.create_auth_hash(self.test_password)

            self.assertIsNotNone(auth_hash)
            result = derivation.verify_password(self.test_password, auth_hash)
            self.assertTrue(result)

    def test_different_memory_cost(self):
        memory_costs = [32768, 65536, 131072]

        for memory_cost in memory_costs:
            derivation = KeyDerivation({
                'argon2_time': 3,
                'argon2_memory': memory_cost,
                'argon2_parallelism': 4
            })

            auth_hash = derivation.create_auth_hash(self.test_password)

            self.assertIsNotNone(auth_hash)
            result = derivation.verify_password(self.test_password, auth_hash)
            self.assertTrue(result)

    def test_different_parallelism(self):
        parallelism_values = [1, 2, 4]

        for parallelism in parallelism_values:
            derivation = KeyDerivation({
                'argon2_time': 3,
                'argon2_memory': 65536,
                'argon2_parallelism': parallelism
            })

            auth_hash = derivation.create_auth_hash(self.test_password)

            self.assertIsNotNone(auth_hash)
            result = derivation.verify_password(self.test_password, auth_hash)
            self.assertTrue(result)

    def test_all_combinations(self):
        test_cases = [
            {"time_cost": 2, "memory_cost": 32768, "parallelism": 1},
            {"time_cost": 3, "memory_cost": 65536, "parallelism": 2},
            {"time_cost": 4, "memory_cost": 131072, "parallelism": 4},
        ]

        for params in test_cases:
            derivation = KeyDerivation({
                'argon2_time': params["time_cost"],
                'argon2_memory': params["memory_cost"],
                'argon2_parallelism': params["parallelism"]
            })

            auth_hash = derivation.create_auth_hash(self.test_password)

            self.assertIsNotNone(auth_hash)
            result = derivation.verify_password(self.test_password, auth_hash)
            self.assertTrue(result)


class TestPasswordStrength(unittest.TestCase):

    def setUp(self):
        self.auth = AuthenticationService(":memory:")

    def test_weak_passwords(self):
        weak_passwords = [
            "short",
            "password123",
            "qwerty123",
            "12345678",
            "onlylowercase",
            "ONLYUPPERCASE",
            "NoDigits!",
            "NoSpecial123"
        ]

        for password in weak_passwords:
            is_strong, errors = self.auth._check_password_strength(password)
            self.assertFalse(is_strong)
            self.assertGreater(len(errors), 0)

    def test_strong_passwords(self):
        strong_passwords = [
            "StrongP@ssw0rd123",
            "C0mpl3x!P@ss",
            "VeryStr0ng!Password",
            "P@ssw0rdWithNum123",
            "Test123!@#Test",
            "MyP@ssw0rdStr0ng!",
            "SecureP@ss2024!"
        ]

        for password in strong_passwords:
            is_strong, errors = self.auth._check_password_strength(password)
            self.assertTrue(is_strong, f"Пароль '{password}' должен быть надежным. Ошибки: {errors}")


if __name__ == "__main__":
    unittest.main()