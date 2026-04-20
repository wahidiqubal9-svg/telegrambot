import sqlite3

DB_FILE = 'bot_database.db'

import os

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    # telegram_id: Unique ID of the user
    # referred_by: Telegram ID of the person who invited them (NULL if none)
    # is_verified: 1 if they have subscribed to both channel and group, 0 otherwise
    # has_claimed_reward: 1 if they have already generated their private link
    # last_message_id: Stores the ID of the last menu message sent to the user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            referred_by INTEGER,
            is_verified INTEGER DEFAULT 0,
            has_claimed_reward INTEGER DEFAULT 0,
            last_message_id INTEGER DEFAULT NULL
        )
    ''')

    # Add last_message_id to existing users table if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN last_message_id INTEGER DEFAULT NULL')
    except sqlite3.OperationalError:
        pass # Column already exists

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
            PRIMARY KEY (telegram_id, chat_id),
            FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
        )
    ''')

    conn.commit()

    # Initialize config and required_chats from env if empty
    cursor.execute('SELECT COUNT(*) FROM config')
    if cursor.fetchone()[0] == 0:
        private_channel_id = os.getenv("PRIVATE_CHANNEL_ID", "")
        required_referrals = os.getenv("REQUIRED_REFERRALS", "10")
        welcome_message = os.getenv("WELCOME_MESSAGE", "Welcome! To gain access to our exclusive Private Channel, you need to:\n\n1. Subscribe to our required channels\n2. Invite {required_referrals} friends using your referral link who also complete step 1.\n\nUse the buttons below to navigate.")
        cursor.execute('INSERT INTO config (key, value) VALUES (?, ?)', ("PRIVATE_CHANNEL_ID", private_channel_id))
        cursor.execute('INSERT INTO config (key, value) VALUES (?, ?)', ("REQUIRED_REFERRALS", required_referrals))
        cursor.execute('INSERT INTO config (key, value) VALUES (?, ?)', ("WELCOME_MESSAGE", welcome_message))
        conn.commit()
    else:
        # Check if WELCOME_MESSAGE exists, if not insert default
        cursor.execute('SELECT COUNT(*) FROM config WHERE key = ?', ("WELCOME_MESSAGE",))
        if cursor.fetchone()[0] == 0:
            welcome_message = os.getenv("WELCOME_MESSAGE", "Welcome! To gain access to our exclusive Private Channel, you need to:\n\n1. Subscribe to our required channels\n2. Invite {required_referrals} friends using your referral link who also complete step 1.\n\nUse the buttons below to navigate.")
            cursor.execute('INSERT INTO config (key, value) VALUES (?, ?)', ("WELCOME_MESSAGE", welcome_message))
            conn.commit()

    cursor.execute('SELECT COUNT(*) FROM required_chats')
    if cursor.fetchone()[0] == 0:
        public_channel_id = os.getenv("PUBLIC_CHANNEL_ID", "@neetpgfmgemcqhourly")
        public_channel_link = os.getenv("PUBLIC_CHANNEL_LINK", "https://t.me/neetpgfmgemcqhourly")
        public_group_id = os.getenv("PUBLIC_GROUP_ID", "@neetpgpyqhourly")
        public_group_link = os.getenv("PUBLIC_GROUP_LINK", "https://t.me/neetpgpyqhourly")

        if public_channel_id and public_channel_link:
            cursor.execute('INSERT INTO required_chats (chat_id, link) VALUES (?, ?)', (public_channel_id, public_channel_link))
        if public_group_id and public_group_link:
            cursor.execute('INSERT INTO required_chats (chat_id, link) VALUES (?, ?)', (public_group_id, public_group_link))
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
    cursor.execute('SELECT telegram_id, referred_by, is_verified, has_claimed_reward, last_message_id FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            'telegram_id': user[0],
            'referred_by': user[1],
            'is_verified': bool(user[2]),
            'has_claimed_reward': bool(user[3]),
            'last_message_id': user[4]
        }
    return None

def update_last_message_id(telegram_id: int, message_id: int):
    """Update the last message ID sent to the user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_message_id = ? WHERE telegram_id = ?', (message_id, telegram_id))
    conn.commit()
    conn.close()

def get_last_message_id(telegram_id: int):
    """Get the last message ID sent to the user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT last_message_id FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def mark_verified(telegram_id: int):
    """Mark a user as verified (subscribed to both public channel and group)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_verified = 1 WHERE telegram_id = ?', (telegram_id,))
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

def get_all_referrers():
    """Get a list of users who have made successful referrals, ordered by highest count."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Count how many verified users each referred_by has
    cursor.execute('''
        SELECT referred_by, COUNT(*) as count
        FROM users
        WHERE referred_by IS NOT NULL AND is_verified = 1
        GROUP BY referred_by
        ORDER BY count DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return [{'telegram_id': row[0], 'referrals': row[1]} for row in results]

def mark_reward_claimed(telegram_id: int):
    """Mark that a user has already claimed their private link."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET has_claimed_reward = 1 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

def get_config(key: str, default=None):
    """Get a configuration value."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_config(key: str, value: str):
    """Set a configuration value."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_required_chats():
    """Get all required chats."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, chat_id, link FROM required_chats')
    chats = [{'id': row[0], 'chat_id': row[1], 'link': row[2]} for row in cursor.fetchall()]
    conn.close()
    return chats

def add_required_chat(chat_id: str, link: str):
    """Add a required chat."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO required_chats (chat_id, link) VALUES (?, ?)', (chat_id, link))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_required_chat(chat_id_db: int):
    """Remove a required chat by its database ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM required_chats WHERE id = ?', (chat_id_db,))
    conn.commit()
    conn.close()

def get_user_verified_chats(telegram_id: int):
    """Get the specific chats a user has verified against."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM user_verified_chats WHERE telegram_id = ?', (telegram_id,))
    chats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chats

def add_user_verified_chat(telegram_id: int, chat_id: str):
    """Record that a user has verified against a specific chat."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_verified_chats (telegram_id, chat_id) VALUES (?, ?)', (telegram_id, chat_id))
    conn.commit()
    conn.close()
