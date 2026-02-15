from .abstract import EncryptionService


class XORPlaceholderEncryption(EncryptionService):

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        return self._xor(data, key)

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        return self._xor(data, key)

    def _xor(self, data: bytes, key: bytes) -> bytes:
        result = bytearray()
        for i in range(len(data)):
            result.append(data[i] ^ key[i % len(key)])
        return bytes(result)
