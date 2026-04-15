import sqlite3

DB_FILE = 'bot_database.db'

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    # telegram_id: Unique ID of the user
    # referred_by: Telegram ID of the person who invited them (NULL if none)
    # is_verified: 1 if they have subscribed to both channel and group, 0 otherwise
    # has_claimed_reward: 1 if they have already generated their private link
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            referred_by INTEGER,
            is_verified INTEGER DEFAULT 0,
            has_claimed_reward INTEGER DEFAULT 0
        )
    ''')

    # Create config table for single-value settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Create required_chats table for dynamic channels/groups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS required_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_name TEXT,
            chat_id TEXT,
            chat_link TEXT
        )
    ''')

    # Create user_verified_chats table to track WHICH chats a user is verified against
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_verified_chats (
            telegram_id INTEGER,
            chat_id TEXT,
            PRIMARY KEY (telegram_id, chat_id)
        )
    ''')

    conn.commit()
    conn.close()

def get_config(key: str, default=None):
    """Get a configuration value from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_config(key: str, value: str):
    """Set a configuration value in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def get_all_required_chats():
    """Get all required channels/groups."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, chat_name, chat_id, chat_link FROM required_chats')
    chats = [{'id': row[0], 'chat_name': row[1], 'chat_id': row[2], 'chat_link': row[3]} for row in cursor.fetchall()]
    conn.close()
    return chats

def add_required_chat(chat_name: str, chat_id: str, chat_link: str):
    """Add a new required channel/group."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO required_chats (chat_name, chat_id, chat_link) VALUES (?, ?, ?)', (chat_name, chat_id, chat_link))
    conn.commit()
    conn.close()

def remove_required_chat(chat_db_id: int):
    """Remove a required channel/group by its database ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM required_chats WHERE id = ?', (chat_db_id,))
    conn.commit()
    conn.close()

def clear_user_verification(telegram_id: int):
    """Un-verify a user (used if they leave a required chat)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_verified = 0 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

def add_user(telegram_id: int, referred_by: int = None):
    """Add a new user to the database if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Check if user already exists
    cursor.execute('SELECT telegram_id FROM users WHERE telegram_id = ?', (telegram_id,))
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users (telegram_id, referred_by) VALUES (?, ?)', (telegram_id, referred_by))
        conn.commit()

    conn.close()

def get_user(telegram_id: int):
    """Get user data."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id, referred_by, is_verified, has_claimed_reward FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            'telegram_id': user[0],
            'referred_by': user[1],
            'is_verified': bool(user[2]),
            'has_claimed_reward': bool(user[3])
        }
    return None

def mark_verified(telegram_id: int):
    """Mark a user as verified."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_verified = 1 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

def add_user_verified_chat(telegram_id: int, chat_id: str):
    """Record that a user was verified for a specific chat."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_verified_chats (telegram_id, chat_id) VALUES (?, ?)', (telegram_id, str(chat_id)))
    conn.commit()
    conn.close()

def get_user_verified_chats(telegram_id: int):
    """Get the specific chat IDs a user was verified against."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM user_verified_chats WHERE telegram_id = ?', (telegram_id,))
    chat_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chat_ids

def clear_user_verified_chats(telegram_id: int):
    """Remove all verified chat records for a user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_verified_chats WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

def get_successful_referrals_count(telegram_id: int) -> int:
    """Get the count of verified users who were referred by this user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Count how many users have referred_by = telegram_id AND is_verified = 1
    cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ? AND is_verified = 1', (telegram_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def mark_reward_claimed(telegram_id: int):
    """Mark that a user has already claimed their private link."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET has_claimed_reward = 1 WHERE telegram_id = ?', (telegram_id,))
    cursor.execute('DELETE FROM user_verified_chats WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()
