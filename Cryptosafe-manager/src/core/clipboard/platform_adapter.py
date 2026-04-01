from abc import ABC, abstractmethod
import platform
from typing import Optional


class ClipboardAdapter(ABC):

    @abstractmethod
    def copy_to_clipboard(self, data: str) -> bool:
        pass

    @abstractmethod
    def clear_clipboard(self) -> bool:
        pass

    @abstractmethod
    def get_clipboard_content(self) -> Optional[str]:
        pass


class WindowsClipboardAdapter(ClipboardAdapter):
    def __init__(self):
        try:
            import win32clipboard
            import win32con
            self.win32clipboard = win32clipboard
            self.win32con = win32con
            self._available = True
            print("[ADAPTER] Windows адаптер инициализирован")
        except ImportError:
            self._available = False
            print("[ADAPTER] win32clipboard не установлен")

    def copy_to_clipboard(self, data: str) -> bool:
        print(f"[ADAPTER] Windows copy_to_clipboard вызван, data={data[:20]}...")
        if not self._available:
            print("[ADAPTER] Адаптер не доступен")
            return False

        try:
            self.win32clipboard.OpenClipboard()
            self.win32clipboard.EmptyClipboard()
            self.win32clipboard.SetClipboardText(data, self.win32clipboard.CF_UNICODETEXT)
            self.win32clipboard.CloseClipboard()
            print("[ADAPTER] Windows копирование УСПЕШНО")
            return True
        except Exception as e:
            print(f"[ADAPTER] Windows copy error: {e}")
            try:
                self.win32clipboard.CloseClipboard()
            except:
                pass
            return False

    def clear_clipboard(self) -> bool:
        if not self._available:
            return False
        try:
            self.win32clipboard.OpenClipboard()
            self.win32clipboard.EmptyClipboard()
            self.win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            print(f"Windows clear error: {e}")
            try:
                self.win32clipboard.CloseClipboard()
            except:
                pass
            return False

    def get_clipboard_content(self) -> Optional[str]:
        if not self._available:
            return None

        try:
            self.win32clipboard.OpenClipboard()
            if self.win32clipboard.IsClipboardFormatAvailable(self.win32clipboard.CF_UNICODETEXT):
                data = self.win32clipboard.GetClipboardText()
                self.win32clipboard.CloseClipboard()
                return data
            self.win32clipboard.CloseClipboard()
            return None
        except Exception as e:
            print(f"Windows get error: {e}")
            try:
                self.win32clipboard.CloseClipboard()
            except:
                pass
            return None


class MacOSClipboardAdapter(ClipboardAdapter):

    def __init__(self):
        try:
            from Foundation import NSPasteboard
            from AppKit import NSPasteboardTypeString
            self.NSPasteboard = NSPasteboard
            self.NSPasteboardTypeString = NSPasteboardTypeString
            self._available = True
            print("[ADAPTER] macOS адаптер инициализирован")
        except ImportError:
            self._available = False
            print("[ADAPTER] pyobjc не установлен")

    def copy_to_clipboard(self, data: str) -> bool:
        print(f"[ADAPTER] macOS copy_to_clipboard вызван, data={data[:20]}...")
        if not self._available:
            print("[ADAPTER] Адаптер не доступен")
            return False

        try:
            pb = self.NSPasteboard.generalPasteboard()
            pb.declareTypes_owner_([self.NSPasteboardTypeString], None)
            pb.setString_forType_(data, self.NSPasteboardTypeString)
            print("[ADAPTER] macOS копирование УСПЕШНО")
            return True
        except Exception as e:
            print(f"[ADAPTER] macOS copy error: {e}")
            return False

    def clear_clipboard(self) -> bool:
        if not self._available:
            return False

        try:
            pb = self.NSPasteboard.generalPasteboard()
            pb.clearContents()
            return True
        except Exception as e:
            print(f"MacOS clear error: {e}")
            return False

    def get_clipboard_content(self) -> Optional[str]:
        if not self._available:
            return None

        try:
            pb = self.NSPasteboard.generalPasteboard()
            return pb.stringForType_(self.NSPasteboardTypeString)
        except Exception as e:
            print(f"MacOS get error: {e}")
            return None


class LinuxClipboardAdapter(ClipboardAdapter):

    def __init__(self):
        try:
            import pyperclip
            self.pyperclip = pyperclip
            self._available = True
            print("[ADAPTER] Linux адаптер инициализирован (pyperclip)")
        except ImportError:
            self._available = False
            print("[ADAPTER] Pyperclip не установлен")

    def copy_to_clipboard(self, data: str) -> bool:
        print(f"[ADAPTER] Linux copy_to_clipboard вызван, data={data[:20]}...")
        if not self._available:
            print("[ADAPTER] Адаптер не доступен")
            return False

        try:
            self.pyperclip.copy(data)
            print("[ADAPTER] Linux копирование УСПЕШНО")
            return True
        except Exception as e:
            print(f"[ADAPTER] Linux copy error: {e}")
            return False

    def clear_clipboard(self) -> bool:
        if not self._available:
            return False

        try:
            self.pyperclip.copy("")
            return True
        except Exception as e:
            print(f"Linux clear error: {e}")
            return False

    def get_clipboard_content(self) -> Optional[str]:
        if not self._available:
            return None

        try:
            return self.pyperclip.paste()
        except Exception as e:
            print(f"Linux get error: {e}")
            return None


class FallbackClipboardAdapter(ClipboardAdapter):

    def __init__(self):
        try:
            import pyperclip
            self.pyperclip = pyperclip
            self._available = True
            print("[ADAPTER] Fallback адаптер инициализирован (pyperclip)")
        except ImportError:
            self._available = False
            print("[ADAPTER] Pyperclip не установлен, базовая функциональность недоступна")

    def copy_to_clipboard(self, data: str) -> bool:
        print(f"[ADAPTER] Fallback copy_to_clipboard вызван, data={data[:20]}...")
        if not self._available:
            print("[ADAPTER] Нет доступного адаптера для копирования")
            return False

        try:
            self.pyperclip.copy(data)
            print("[ADAPTER] Fallback копирование УСПЕШНО")
            return True
        except Exception as e:
            print(f"[ADAPTER] Fallback copy error: {e}")
            return False

    def clear_clipboard(self) -> bool:
        if not self._available:
            return False

        try:
            self.pyperclip.copy("")
            return True
        except Exception as e:
            print(f"[ADAPTER] Fallback clear error: {e}")
            return False

    def get_clipboard_content(self) -> Optional[str]:
        if not self._available:
            return None

        try:
            return self.pyperclip.paste()
        except Exception as e:
            print(f"[ADAPTER] Fallback get error: {e}")
            return None


def get_platform_adapter() -> ClipboardAdapter:
    system = platform.system()
    print(f"[ADAPTER] Определена платформа: {system}")

    if system == "Windows":
        adapter = WindowsClipboardAdapter()
        if adapter._available:
            print("[ADAPTER] Используется Windows адаптер")
            return adapter
        else:
            print("[ADAPTER] Windows адаптер не доступен, пробуем fallback")

    elif system == "Darwin":
        adapter = MacOSClipboardAdapter()
        if adapter._available:
            print("[ADAPTER] Используется macOS адаптер")
            return adapter
        else:
            print("[ADAPTER] macOS адаптер не доступен, пробуем fallback")

    elif system == "Linux":
        adapter = LinuxClipboardAdapter()
        if adapter._available:
            print("[ADAPTER] Используется Linux адаптер")
            return adapter
        else:
            print("[ADAPTER] Linux адаптер не доступен, пробуем fallback")

    print("[ADAPTER] Используется Fallback адаптер")
    return FallbackClipboardAdapter()