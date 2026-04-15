import sqlite3
import os

DB_FILE = 'bot_database.db'

def update_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create config table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Create required_chats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS required_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            link TEXT
        )
    ''')

    # Create user_verified_chats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_verified_chats (
            telegram_id INTEGER,
            chat_id TEXT,
            PRIMARY KEY (telegram_id, chat_id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_db()
