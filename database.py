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

def mark_reward_claimed(telegram_id: int):
    """Mark that a user has already claimed their private link."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET has_claimed_reward = 1 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()
