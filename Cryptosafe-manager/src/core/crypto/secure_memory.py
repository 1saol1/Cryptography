import ctypes
import logging
import platform

logger = logging.getLogger(__name__)


class SecureMemory:

    def __init__(self):
        self._allocated_buffers = []

        self.MEM_COMMIT = 0x1000
        self.MEM_RESERVE = 0x2000
        self.PAGE_READWRITE = 0x04
        self.MEM_RELEASE = 0x8000

        self.system = platform.system()
        self._init_platform_functions()

    def _init_platform_functions(self):

        if self.system == "Windows":
            try:
                self.kernel32 = ctypes.windll.kernel32

                self.VirtualAlloc = self.kernel32.VirtualAlloc
                self.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                              ctypes.c_ulong, ctypes.c_ulong]
                self.VirtualAlloc.restype = ctypes.c_void_p

                self.VirtualFree = self.kernel32.VirtualFree
                self.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]
                self.VirtualFree.restype = ctypes.c_bool

                self.VirtualLock = self.kernel32.VirtualLock
                self.VirtualLock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                self.VirtualLock.restype = ctypes.c_bool

                self.VirtualUnlock = self.kernel32.VirtualUnlock
                self.VirtualUnlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                self.VirtualUnlock.restype = ctypes.c_bool

                try:
                    self.crypt32 = ctypes.windll.crypt32
                    self.CryptProtectMemory = self.crypt32.CryptProtectMemory
                    self.CryptProtectMemory.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]
                    self.CryptProtectMemory.restype = ctypes.c_bool
                    self._crypt_available = True
                except:
                    self._crypt_available = False

                logger.info("[SecureMemory] Windows API инициализирован")

            except Exception as e:
                logger.warning(f"[SecureMemory] Ошибка инициализации Windows API: {e}")
                self._fallback_mode = True

        else:
            try:
                self.libc = ctypes.CDLL("libc.so.6")
            except:
                try:
                    self.libc = ctypes.CDLL("libc.dylib")
                except:
                    self.libc = None

            if self.libc:
                self.mlock = self.libc.mlock
                self.mlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                self.mlock.restype = ctypes.c_int

                self.munlock = self.libc.munlock
                self.munlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
                self.munlock.restype = ctypes.c_int

                logger.info("[SecureMemory] Unix API инициализирован")
            else:
                logger.warning("[SecureMemory] libc не найдена")

    def secure_alloc(self, size: int) -> ctypes.c_void_p:

        if size == 0:
            return None

        if self.system == "Windows":
            try:
                ptr = self.VirtualAlloc(
                    None,
                    size,
                    self.MEM_COMMIT | self.MEM_RESERVE,
                    self.PAGE_READWRITE
                )

                if ptr:
                    if hasattr(self, '_crypt_available') and self._crypt_available:
                        self.CryptProtectMemory(ptr, size, 0)

                    self.VirtualLock(ptr, size)

                    logger.debug(f"[SecureMemory] Выделено {size} байт non-pageable памяти")
                    return ptr
                else:
                    error = ctypes.GetLastError()
                    logger.warning(f"[SecureMemory] VirtualAlloc failed: error={error}")
                    return None

            except Exception as e:
                logger.warning(f"[SecureMemory] Ошибка выделения памяти: {e}")
                return None

        else:
            try:
                import mmap

                flags = mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS

                if hasattr(mmap, 'MAP_LOCKED'):
                    flags |= mmap.MAP_LOCKED

                ptr = mmap.mmap(
                    -1,
                    size,
                    flags,
                    mmap.PROT_READ | mmap.PROT_WRITE
                )

                if not hasattr(mmap, 'MAP_LOCKED') and self.libc:
                    address = ctypes.addressof(ctypes.py_object(ptr))
                    self.mlock(address, size)

                logger.debug(f"[SecureMemory] Выделено {size} байт (mmap)")
                return ptr

            except Exception as e:
                logger.warning(f"[SecureMemory] mmap error: {e}")
                return None

    def secure_free(self, ptr, size: int):

        if not ptr:
            return

        try:
            if self.system == "Windows":
                ctypes.memset(ptr, 0, size)
                self.VirtualUnlock(ptr, size)
                self.VirtualFree(ptr, 0, self.MEM_RELEASE)
            else:
                if hasattr(ptr, 'close'):
                    ptr.close()

            logger.debug(f"[SecureMemory] Освобождено {size} байт")

        except Exception as e:
            logger.warning(f"[SecureMemory] Ошибка освобождения памяти: {e}")

    def secure_store(self, data: bytes) -> bytearray:

        if not data:
            return bytearray()

        size = len(data)

        ptr = self.secure_alloc(size)

        if ptr:
            if self.system == "Windows":
                ctypes.memmove(ptr, data, size)

                result = bytearray(ctypes.string_at(ptr, size))

                self._allocated_buffers.append((ptr, size, result))

                return result
            else:
                if hasattr(ptr, 'write'):
                    ptr.write(data)
                    ptr.seek(0)
                    result = bytearray(ptr.read(size))
                    self._allocated_buffers.append((ptr, size, result))
                    return result

        logger.warning("[SecureMemory] Non-pageable память недоступна, используется fallback")
        result = bytearray(data)

        try:
            addr = ctypes.addressof(ctypes.py_object(result))
            self.lock_memory(addr, size)
        except:
            pass

        return result

    def lock_memory(self, address: int, size: int) -> bool:

        if self.system == "Windows":
            try:
                result = self.VirtualLock(ctypes.c_void_p(address), size)
                if result:
                    logger.debug(f"VirtualLock успешен, размер={size}")
                    return True
                else:
                    logger.warning(f"VirtualLock failed")
                    return False
            except Exception as e:
                logger.warning(f"VirtualLock недоступен: {e}")
                return False
        else:
            if not self.libc:
                return False
            try:
                result = self.mlock(ctypes.c_void_p(address), size)
                if result == 0:
                    logger.debug(f"mlock успешен, размер={size}")
                    return True
                else:
                    logger.warning(f"mlock failed, result={result}")
                    return False
            except Exception as e:
                logger.warning(f"mlock недоступен: {e}")
                return False

    def unlock_memory(self, address: int, size: int):

        if self.system == "Windows":
            try:
                self.VirtualUnlock(ctypes.c_void_p(address), size)
                logger.debug(f"VirtualUnlock успешен")
            except Exception as e:
                logger.warning(f"VirtualUnlock недоступен: {e}")
        else:
            if not self.libc:
                return
            try:
                self.munlock(ctypes.c_void_p(address), size)
                logger.debug(f"munlock успешен")
            except Exception as e:
                logger.warning(f"munlock недоступен: {e}")

    def zero_memory(self, address, size: int):

        try:
            ctypes.memset(ctypes.c_void_p(address), 0, size)
            logger.debug(f"Память обнулена, размер={size}")
        except Exception as e:
            logger.warning(f"Ошибка обнуления памяти: {e}")

    def secure_clear(self, data):

        if not data:
            return

        for ptr, size, buf in self._allocated_buffers:
            if buf is data:
                try:
                    if self.system == "Windows":
                        ctypes.memset(ptr, 0, size)
                        self.VirtualUnlock(ptr, size)
                        self.VirtualFree(ptr, 0, self.MEM_RELEASE)
                    else:
                        if hasattr(ptr, 'close'):
                            ptr.close()
                    logger.debug(f"Буфер очищен и освобождён")
                except Exception as e:
                    logger.warning(f"Ошибка очистки буфера: {e}")

        if isinstance(data, bytearray):
            for i in range(len(data)):
                data[i] = 0

        self._allocated_buffers = []
        logger.debug("Память успешно затерта")

    def __del__(self):
        for ptr, size, buf in self._allocated_buffers:
            try:
                if self.system == "Windows":
                    ctypes.memset(ptr, 0, size)
                    self.VirtualFree(ptr, 0, self.MEM_RELEASE)
                else:
                    if hasattr(ptr, 'close'):
                        ptr.close()
            except:
                pass