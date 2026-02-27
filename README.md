# CryptoSafe Manager

CryptoSafe Manager — это безопасный менеджер паролей с локальной зашифрованной базой данных (SQLite), реализованный на Python + Tkinter.  

Проект разрабатывается в рамках учебного курса и состоит из 8 последовательных спринтов, каждый из которых добавляет новые функции безопасности и удобства.

Основная цель — создать безопасное локальное хранилище,
защищённое мастер-паролем и криптографией.

#  Roadmap (8 Sprints)

##  Sprint 1 — Architecture & Foundation
- Структура проекта
- SQLite база данных
- EventBus
- Заглушка шифрования (XOR placeholder)
- GUI (Tkinter)
- Setup Window (создание мастер-пароля)
- README + архитектурная документация

##  Sprint 2 — Authentication & Key Management
- Master password hashing (salt + PBKDF2)
- Key derivation
- Session management
- Login window
- Хранение auth_hash в key_store

##  Sprint 3 — Real Encryption
- Замена XOR на AES
- Secure memory handling
- Key rotation support

##  Sprint 4 — Secure Storage
- Шифрование записей в БД
- Разделение metadata и encrypted payload

##  Sprint 5 — Advanced Security
- Brute-force protection
- Exponential backoff
- Audit improvements

##  Sprint 6 — UX & Improvements
- Автоблокировка
- Clipboard timeout
- Password strength checker

##  Sprint 7 — Testing & Hardening
- Unit tests coverage
- Edge-case testing
- Code cleanup

##  Sprint 8 — Final Security Review
- Threat modeling
- Security checklist
- Documentation finalization

# Installation Guide

## Clone repository

```bash
git clone <your-repository-url>
cd Cryptosafe-manager
```
## Создайте и активируйте виртуальное окружение

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

## Установите зависимости
```bash
pip install -r requirements.txt
```

## Запустите приложение
```bash
python src/gui/main_window.py
```
# Архитектура проекта (MVC-подобная)
                +-------------------+
                |   GUI (Tkinter)   |
                |  main_window.py   |
                |     widgets/      |
                +-------------------+
                         ↑↓
                +-------------------+
                |  EventBus         |
                |  StateManager     |
                +-------------------+
                         ↑↓
   +-----------------------------------+
   |          Business Logic           |
   |  core/crypto (шифрование)         |
   |  database (SQLite + модели)       |
   +-----------------------------------+
