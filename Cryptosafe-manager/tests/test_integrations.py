import pytest
from src.database.db import Database
from src.core.crypto.authentication import AuthenticationService
from src.core.state_manager import StateManager


def test_initial_setup_and_login_flow(tmp_path):

    db_path = tmp_path / "test_cryptosafe.db"
    db = Database(str(db_path))
    db.initialize()

    auth = AuthenticationService(str(db_path))
    session = StateManager()

    assert not auth.is_initialized()

    auth.register("testpassword123")

    assert auth.is_initialized()

    key = auth.login("testpassword123")
    assert key is not None, "Логин с правильным паролем должен вернуть ключ"

    wrong_key = auth.login("wrongpass")
    assert wrong_key is None, "Логин с неверным паролем должен вернуть None"

    # Проверяем, что сессия может стартовать
    session.start_session(key)
    assert session.is_active(), "Сессия должна быть активной после start_session"

    db.close()


def test_main_window_launch_after_login(tmp_path, mocker):

    from src.gui.main_window import main  # или импортируй CryptoSafeApp

    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    db.initialize()

    auth = AuthenticationService(str(db_path))
    auth.register("testpass")  # симулируем настройку

    session = StateManager()

    # Мокаем show_login_window — возвращаем успешный логин
    mocker.patch(
        "src.gui.main_window.show_login_window",
        return_value=True
    )


    mocker.patch("tkinter.Tk.deiconify")
    mocker.patch("tkinter.Tk.mainloop")

    # Запускаем main() — должно пройти без ошибок
    try:
        main()
    except Exception as e:
        pytest.fail(f"Запуск main() упал: {e}")

    assert True  # если дошло сюда — запуск прошёл