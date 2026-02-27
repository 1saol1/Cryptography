import pytest
from src.database.db import Database


def test_database_connection(test_db):
    assert test_db.connection is not None
    assert test_db.cursor is not None
    assert isinstance(test_db.connection, sqlite3.Connection)


def test_database_tables_created(test_db):
    cursor = test_db.cursor
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%';
    """)
    tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        'vault_entries',
        'audit_log',
    }

    assert expected_tables.issubset(tables)


def test_vault_entries_table_schema(test_db):
    cursor = test_db.cursor
    cursor.execute("PRAGMA table_info(vault_entries);")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        'id', 'title', 'username', 'encrypted_password',
        'url', 'notes', 'created_at', 'updated_at', 'tags'
    }

    assert expected_columns.issubset(columns)


def test_audit_log_table_schema(test_db):
    cursor = test_db.cursor
    cursor.execute("PRAGMA table_info(audit_log);")
    columns = {row[1] for row in cursor.fetchall()}

    expected_columns = {
        'id', 'action', 'timestamp', 'entry_id', 'details', 'signature'
    }

    assert expected_columns.issubset(columns)


def test_insert_and_select_vault_entry(test_db):
    cursor = test_db.cursor
    conn = test_db.connection

    cursor.execute("""
        INSERT INTO vault_entries (title, username, encrypted_password, url, notes)
        VALUES (?, ?, ?, ?, ?)
    """, ("Test Site", "testuser", b"encrypted_pass", "https://test.com", "Some note"))

    conn.commit()

    cursor.execute("SELECT title, username, url FROM vault_entries WHERE title = 'Test Site'")
    row = cursor.fetchone()

    assert row is not None
    assert row[0] == "Test Site"
    assert row[1] == "testuser"
    assert row[2] == "https://test.com"