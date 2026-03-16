import unittest
import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.core.crypto.key_derivation import KeyDerivation


class TestTimeAttack(unittest.TestCase):

    def setUp(self):
        self.derivation = KeyDerivation()
        self.password = "MyStrongPassword123!"
        self.wrong_password = "WrongPassword123!"

    def test_constant_time_comparison(self):

        auth_hash = self.derivation.create_auth_hash(self.password)

        start = time.time()
        self.derivation.verify_password(self.password, auth_hash)
        correct_time = time.time() - start

        start = time.time()
        self.derivation.verify_password(self.wrong_password, auth_hash)
        wrong_time = time.time() - start


        time_diff = abs(correct_time - wrong_time)
        print(f"\nВремя проверки правильного пароля: {correct_time:.6f} сек")
        print(f"Время проверки неправильного пароля: {wrong_time:.6f} сек")
        print(f"Разница: {time_diff:.6f} сек")

        self.assertLess(time_diff, 0.1)

    # проверяем, что время для разных неверных паролей одинаковое
    def test_multiple_wrong_passwords(self):

        auth_hash = self.derivation.create_auth_hash(self.password)

        wrong_passwords = [
            "Wrong1!",
            "VeryLongWrongPassword1234567890!",
            "AlmostCorrect!",
            "CompletelyDifferent",
            "Short"
        ]

        times = []
        for pwd in wrong_passwords:
            start = time.time()
            self.derivation.verify_password(pwd, auth_hash)
            times.append(time.time() - start)

        print("\nВремя для разных неправильных паролей:")
        for i, t in enumerate(times):
            print(f"  Пароль {i + 1}: {t:.6f} сек")

        avg_time = sum(times) / len(times)
        for t in times:
            diff = abs(t - avg_time)
            self.assertLess(diff, 0.05)


if __name__ == "__main__":
    unittest.main()