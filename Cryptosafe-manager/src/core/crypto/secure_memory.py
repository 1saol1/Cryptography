import sys
import ctypes
import logging

logger = logging.getLogger(__name__)


class SecureMemory:
    def __init__(self):
        self._stored_data = None
        self._locked = False

    @staticmethod
    def lock_memory(address, size):
        if sys.platform == 'win32':
            try:
                kernel32 = ctypes.windll.kernel32
                result = kernel32.VirtualLock(ctypes.c_void_p(address), size)
                if result:
                    logger.debug(f"VirtualLock успешен, размер={size}")
                    return True
                else:
                    error = ctypes.GetLastError()
                    logger.warning(f"VirtualLock failed, error={error}")
                    return False
            except Exception as e:
                logger.warning(f"VirtualLock недоступен: {e}")
                return False
        else:
            try:
                libc = ctypes.CDLL("libc.so.6")
            except:
                try:
                    libc = ctypes.CDLL("libc.dylib")
                except:
                    logger.warning("libc не найдена")
                    return False

            try:
                result = libc.mlock(ctypes.c_void_p(address), size)
                if result == 0:
                    logger.debug(f"mlock успешен, размер={size}")
                    return True
                else:
                    logger.warning(f"mlock failed, result={result}")
                    return False
            except Exception as e:
                logger.warning(f"mlock недоступен: {e}")
                return False

    @staticmethod
    def unlock_memory(address, size):
        if sys.platform == 'win32':
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.VirtualUnlock(ctypes.c_void_p(address), size)
                logger.debug(f"VirtualUnlock успешен, размер={size}")
            except Exception as e:
                logger.warning(f"VirtualUnlock недоступен: {e}")
        else:
            try:
                libc = ctypes.CDLL("libc.so.6")
            except:
                try:
                    libc = ctypes.CDLL("libc.dylib")
                except:
                    return

            try:
                libc.munlock(ctypes.c_void_p(address), size)
                logger.debug(f"munlock успешен, размер={size}")
            except Exception as e:
                logger.warning(f"munlock недоступен: {e}")

    @staticmethod
    def zero_memory(address, size):
        try:
            ctypes.memset(ctypes.c_void_p(address), 0, size)
            logger.debug(f"Память обнулена, размер={size}")
        except Exception as e:
            logger.warning(f"[Ошибка обнуления: {e}")

    def secure_store(self, data: bytes) -> bytes:
        self._stored_data = data

        if data:
            try:
                data_id = id(data)
                data_size = len(data)
                self.lock_memory(data_id, data_size)
                self._locked = True
                logger.debug("Данные сохранены и заблокированы")
            except Exception as e:
                logger.warning(f"Не удалось заблокировать память: {e}")

        return data

    def secure_clear(self, data: bytes) -> None:
        if data:
            try:
                if self._locked:
                    data_id = id(data)
                    data_size = len(data)
                    self.unlock_memory(data_id, data_size)
                    self._locked = False

                if isinstance(data, bytearray):
                    for i in range(len(data)):
                        data[i] = 0
                elif isinstance(data, bytes):
                    mutable = bytearray(data)
                    for i in range(len(mutable)):
                        mutable[i] = 0
                    data = bytes(mutable)

                logger.debug("Память успешно затерта")
            except Exception as e:
                logger.error(f"Ошибка при затирании памяти: {e}")

            self._stored_data = None

    def __del__(self):
        if self._stored_data:
            self.secure_clear(self._stored_data)