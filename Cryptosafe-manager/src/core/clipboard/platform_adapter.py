from abc import ABC, abstractmethod
import platform
from typing import Optional
import subprocess
import shutil
import time
import pyperclip

try:
    import win32clipboard
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    win32clipboard = None
    win32con = None

try:
    from Foundation import NSPasteboard
    from AppKit import NSPasteboardTypeString
    MACOS_AVAILABLE = True
except ImportError:
    MACOS_AVAILABLE = False
    NSPasteboard = None
    NSPasteboardTypeString = None


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
        self._available = WIN32_AVAILABLE
        if not self._available:
            print("Ошибка импорта: win32clipboard не установлен")

    def copy_to_clipboard(self, data: str) -> bool:
        if not self._available:
            print("Адаптер не доступен")
            return False

        for attempt in range(3):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, data)
                win32clipboard.CloseClipboard()
                return True
            except Exception as e:
                print(f"Попытка {attempt + 1} ошибка: {e}")
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
                time.sleep(0.1)
        try:
            pyperclip.copy(data)
            return True
        except:
            return False

    def clear_clipboard(self) -> bool:
        if not self._available:
            return False
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            print(f"Windows clear error: {e}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return False

    def get_clipboard_content(self) -> Optional[str]:
        if not self._available:
            return None

        try:
            win32clipboard.OpenClipboard()

            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                handle = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                if handle:
                    data = handle
                    win32clipboard.CloseClipboard()
                    return str(data) if data else None
            win32clipboard.CloseClipboard()
            return None
        except Exception as e:
            print(f"Windows get error: {e}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return None


class MacOSClipboardAdapter(ClipboardAdapter):
    def __init__(self):
        self._available = MACOS_AVAILABLE
        if not self._available:
            print("pyobjc не установлен")

    def copy_to_clipboard(self, data: str, use_private: bool = False) -> bool:
        if not self._available:
            return False

        try:
            if use_private:
                pb = NSPasteboard.pasteboardWithName_("Apple CFPasteboard drag")
            else:
                pb = NSPasteboard.generalPasteboard()

            pb.declareTypes_owner_([NSPasteboardTypeString], None)
            pb.setString_forType_(data, NSPasteboardTypeString)
            return True
        except Exception as e:
            print(f"macOS copy error: {e}")
            return False

    def clear_clipboard(self, clear_private: bool = False) -> bool:
        success = False

        try:
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            success = True
        except:
            pass

        if clear_private:
            try:
                pb = NSPasteboard.pasteboardWithName_("Apple CFPasteboard drag")
                pb.clearContents()
            except:
                pass

        return success

    def get_clipboard_content(self, from_private: bool = False) -> Optional[str]:
        if not self._available:
            return None

        try:
            if from_private:
                pb = NSPasteboard.pasteboardWithName_("Apple CFPasteboard drag")
            else:
                pb = NSPasteboard.generalPasteboard()

            return pb.stringForType_(NSPasteboardTypeString)
        except Exception as e:
            print(f"MacOS get error: {e}")
            return None


class LinuxClipboardAdapter(ClipboardAdapter):
    def __init__(self):
        self._available = True
        self._wayland_available = False
        self._xclip_available = False
        self._xsel_available = False

        self._check_backends()

    def _check_backends(self):
        if shutil.which('wl-copy') and shutil.which('wl-paste'):
            self._wayland_available = True
            print("[LinuxAdapter] Wayland (wl-clipboard) доступен")

        if shutil.which('xclip'):
            self._xclip_available = True
            print("[LinuxAdapter] xclip доступен")

        if shutil.which('xsel'):
            self._xsel_available = True
            print("[LinuxAdapter] xsel доступен")

    def _copy_with_wayland(self, data: str, primary: bool = False) -> bool:
        try:
            if primary:
                proc = subprocess.Popen(['wl-copy', '--primary'], stdin=subprocess.PIPE)
            else:
                proc = subprocess.Popen(['wl-copy'], stdin=subprocess.PIPE)
            proc.communicate(data.encode())
            return proc.returncode == 0
        except Exception as e:
            print(f"[LinuxAdapter] Wayland copy error: {e}")
            return False

    def _copy_with_xclip(self, data: str, primary: bool = False) -> bool:
        try:
            if primary:
                proc = subprocess.Popen(['xclip', '-selection', 'primary', '-i'], stdin=subprocess.PIPE)
            else:
                proc = subprocess.Popen(['xclip', '-selection', 'clipboard', '-i'], stdin=subprocess.PIPE)
            proc.communicate(data.encode())
            return proc.returncode == 0
        except Exception as e:
            print(f"[LinuxAdapter] xclip copy error: {e}")
            return False

    def _copy_with_xsel(self, data: str, primary: bool = False) -> bool:
        try:
            if primary:
                proc = subprocess.Popen(['xsel', '--primary', '-i'], stdin=subprocess.PIPE)
            else:
                proc = subprocess.Popen(['xsel', '--clipboard', '-i'], stdin=subprocess.PIPE)
            proc.communicate(data.encode())
            return proc.returncode == 0
        except Exception as e:
            print(f"[LinuxAdapter] xsel copy error: {e}")
            return False

    def copy_to_clipboard(self, data: str, use_primary: bool = False) -> bool:
        if not data:
            return False

        if self._wayland_available:
            if self._copy_with_wayland(data, use_primary):
                print(f"[LinuxAdapter] Wayland: copied to {'PRIMARY' if use_primary else 'CLIPBOARD'}")
                return True

        if self._xclip_available:
            if self._copy_with_xclip(data, use_primary):
                print(f"[LinuxAdapter] xclip: copied to {'PRIMARY' if use_primary else 'CLIPBOARD'}")
                return True

        if self._xsel_available:
            if self._copy_with_xsel(data, use_primary):
                print(f"[LinuxAdapter] xsel: copied to {'PRIMARY' if use_primary else 'CLIPBOARD'}")
                return True

        try:
            pyperclip.copy(data)
            print(f"[LinuxAdapter] pyperclip fallback: copied to CLIPBOARD")
            return True
        except Exception as e:
            print(f"[LinuxAdapter] All backends failed: {e}")
            return False

    def clear_clipboard(self, clear_primary: bool = True) -> bool:
        success = False

        if self.copy_to_clipboard("", use_primary=False):
            success = True

        if clear_primary and self.copy_to_clipboard("", use_primary=True):
            success = True

        return success

    def get_clipboard_content(self, from_primary: bool = False) -> Optional[str]:
        if self._wayland_available:
            try:
                if from_primary:
                    proc = subprocess.Popen(['wl-paste', '--primary'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    proc = subprocess.Popen(['wl-paste'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = proc.communicate()
                if proc.returncode == 0 and stdout:
                    return stdout.decode()
            except:
                pass

        if self._xclip_available:
            try:
                if from_primary:
                    proc = subprocess.Popen(['xclip', '-selection', 'primary', '-o'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    proc = subprocess.Popen(['xclip', '-selection', 'clipboard', '-o'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = proc.communicate()
                if proc.returncode == 0 and stdout:
                    return stdout.decode()
            except:
                pass

        if self._xsel_available:
            try:
                if from_primary:
                    proc = subprocess.Popen(['xsel', '--primary', '-o'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    proc = subprocess.Popen(['xsel', '--clipboard', '-o'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = proc.communicate()
                if proc.returncode == 0 and stdout:
                    return stdout.decode()
            except:
                pass

        if not from_primary:
            try:
                return pyperclip.paste()
            except:
                pass

        return None


class FallbackClipboardAdapter(ClipboardAdapter):
    def __init__(self):
        self._available = True

    def copy_to_clipboard(self, data: str) -> bool:
        try:
            pyperclip.copy(data)
            return True
        except Exception as e:
            print(f"Fallback copy error: {e}")
            return False

    def clear_clipboard(self) -> bool:
        try:
            pyperclip.copy("")
            return True
        except Exception as e:
            print(f"Fallback clear error: {e}")
            return False

    def get_clipboard_content(self) -> Optional[str]:
        try:
            return pyperclip.paste()
        except Exception as e:
            print(f"Fallback get error: {e}")
            return None


def get_platform_adapter() -> ClipboardAdapter:
    system = platform.system()
    print(f"Определена платформа: {system}")

    if system == "Windows":
        adapter = WindowsClipboardAdapter()
        if adapter._available:
            print("Используется Windows адаптер")
            return adapter
        else:
            print("Windows адаптер не доступен, пробуем fallback")

    elif system == "Darwin":
        adapter = MacOSClipboardAdapter()
        if adapter._available:
            print("Используется macOS адаптер")
            return adapter
        else:
            print("macOS адаптер не доступен, пробуем fallback")

    elif system == "Linux":
        adapter = LinuxClipboardAdapter()
        if adapter._available:
            print("Используется Linux адаптер")
            return adapter
        else:
            print("Linux адаптер не доступен, пробуем fallback")

    print("Используется Fallback адаптер")
    return FallbackClipboardAdapter()