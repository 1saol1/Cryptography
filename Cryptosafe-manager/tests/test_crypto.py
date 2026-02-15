from src.core.crypto.placeholder import XORPlaceholderEncryption
from src.core.crypto.key_manager import KeyManager


def test_xor_encrypt_decrypt():
    crypto = XORPlaceholderEncryption()
    km = KeyManager()

    key = km.derive_key("password123")
    data = b"secret data"

    encrypted = crypto.encrypt(data, key)
    decrypted = crypto.decrypt(encrypted, key)

    assert decrypted == data
