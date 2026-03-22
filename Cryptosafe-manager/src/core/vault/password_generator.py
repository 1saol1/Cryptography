import secrets
import string
import re
from typing import List


class PasswordGenerator:

    LOWERCASE = string.ascii_lowercase
    UPPERCASE = string.ascii_uppercase
    DIGITS = string.digits
    SPECIAL = "!@#$%^&*"

    AMBIGUOUS = "lI1oO0"

    COMMON_PASSWORDS = {
        'password', 'password123', '123456', 'qwerty', 'admin',
        'letmein', 'welcome', 'monkey', 'dragon', 'baseball',
        'football', 'master', 'superman', 'batman', 'hello'
    }

    def __init__(self):
        self._recent_passwords: List[str] = []
        self._max_history = 20

        self.charsets = {
            'lowercase': self.LOWERCASE,
            'uppercase': self.UPPERCASE,
            'digits': self.DIGITS,
            'special': self.SPECIAL
        }


    def generate(self,
                 length: int = 16,
                 use_uppercase: bool = True,
                 use_lowercase: bool = True,
                 use_digits: bool = True,
                 use_special: bool = True,
                 exclude_ambiguous: bool = True) -> str:

        if length < 8:
            length = 8
        if length > 64:
            length = 64

        if not any([use_uppercase, use_lowercase, use_digits, use_special]):
            use_lowercase = True

        allowed_chars = ""
        required_sets = []

        if use_lowercase:
            chars = self._filter_chars(self.LOWERCASE, exclude_ambiguous)
            allowed_chars += chars
            required_sets.append(chars)

        if use_uppercase:
            chars = self._filter_chars(self.UPPERCASE, exclude_ambiguous)
            allowed_chars += chars
            required_sets.append(chars)

        if use_digits:
            chars = self._filter_chars(self.DIGITS, exclude_ambiguous)
            allowed_chars += chars
            required_sets.append(chars)

        if use_special:
            allowed_chars += self.SPECIAL
            required_sets.append(self.SPECIAL)

        password_chars = []

        for charset in required_sets:
            if charset:
                password_chars.append(secrets.choice(charset))

        remaining = length - len(password_chars)
        for _ in range(remaining):
            password_chars.append(secrets.choice(allowed_chars))

        secrets.SystemRandom().shuffle(password_chars)

        password = ''.join(password_chars)

        strength = self.check_strength(password)
        if not strength['is_strong']:

            return self.generate(length, use_uppercase, use_lowercase,
                                 use_digits, use_special, exclude_ambiguous)

        if password in self._recent_passwords:
            return self.generate(length, use_uppercase, use_lowercase,
                                 use_digits, use_special, exclude_ambiguous)

        self._add_to_history(password)

        return password

    def generate_pin(self, length: int = 6) -> str:
        if length < 4:
            length = 4
        if length > 12:
            length = 12

        return self.generate(
            length=length,
            use_uppercase=False,
            use_lowercase=False,
            use_digits=True,
            use_special=False,
            exclude_ambiguous=True
        )

    def check_strength(self, password: str) -> dict:

        score = 0


        if len(password) >= 12:
            score += 2
        elif len(password) >= 8:
            score += 1


        has_lower = bool(re.search(r'[a-z]', password))
        has_upper = bool(re.search(r'[A-Z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*]', password))

        char_types = sum([has_lower, has_upper, has_digit, has_special])
        score += char_types

        if password.lower() in self.COMMON_PASSWORDS:
            score = 0

        elif len(password) < 8:
            score = min(score, 1)

        if re.search(r'(.)\1{3,}', password):
            score -= 1



        sequences = ['123', '234', '345', '456', '567', '678', '789',
                     'abc', 'bcd', 'cde', 'qwe', 'asd', 'zxc']
        for seq in sequences:
            if seq in password.lower():
                score -= 1
                break

        final_score = max(0, min(4, score))

        if final_score >= 3:
            strength = "Надежный"
            is_strong = True
        elif final_score >= 2:
            strength = "Средний"
            is_strong = False
        else:
            strength = "Слабый"
            is_strong = False

        return {
            'score': final_score,
            'strength': strength,
            'is_strong': is_strong,
            'details': {
                'length': len(password),
                'has_lower': has_lower,
                'has_upper': has_upper,
                'has_digit': has_digit,
                'has_special': has_special
            }
        }

    def _filter_chars(self, chars: str, exclude_ambiguous: bool) -> str:
        if not exclude_ambiguous:
            return chars

        result = ''
        for char in chars:
            if char not in self.AMBIGUOUS:
                result += char
        return result

    def _add_to_history(self, password: str):
        self._recent_passwords.append(password)
        if len(self._recent_passwords) > self._max_history:
            self._recent_passwords.pop(0)

