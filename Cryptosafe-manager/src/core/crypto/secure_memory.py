import sys
import ctypes
import logging

logger = logging.getLogger(__name__)


class SecureMemory:

    def __init__(self):
        self._stored_data = None

    def secure_store(self, data: bytes) -> bytes:

        self._stored_data = data
        return data

    def secure_clear(self, data: bytes) -> None:

        if data:
            try:
                if isinstance(data, bytearray):
                    for i in range(len(data)):
                        data[i] = 0
                elif isinstance(data, bytes):
                    mutable = bytearray(data)
                    for i in range(len(mutable)):
                        mutable[i] = 0

                logger.debug("Память успешно затерта")
            except Exception as e:
                logger.error(f"Ошибка при затирании памяти: {e}")

            self._stored_data = None

    def __del__(self):
        if self._stored_data:
            self.secure_clear(self._stored_data)