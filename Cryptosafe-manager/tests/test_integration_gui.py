import tkinter as tk
from src.gui.main_window import CryptoSafeApp


def test_main_window_creation():
    root = tk.Tk()
    root.withdraw()

    app = CryptoSafeApp(root)

    assert app is not None
    assert app.root.title() == "CryptoSafe Manager"

    root.destroy()