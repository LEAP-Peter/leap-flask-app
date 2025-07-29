import os
import sqlite3

def get_connection():
    """
    返回一个连接到 instance/user_data.db 的 SQLite3 连接。
    如果 instance 目录不存在，会先创建它。
    """
    base_dir = os.getcwd()
    instance_dir = os.path.join(base_dir, 'instance')
    if not os.path.isdir(instance_dir):
        os.makedirs(instance_dir)
    db_path = os.path.join(instance_dir, 'user_data.db')
    conn = sqlite3.connect(db_path)
    # 这样可以让 fetchone/fetchall 返回的都是 dict-like 的 Row
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """
    在第一次启动或需要重建时调用，确保所有表和必要的列都存在。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 创建 users 表，含持久化 star_color 字段
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            real_name TEXT    NOT NULL,
            username  TEXT    NOT NULL UNIQUE,
            email     TEXT    NOT NULL UNIQUE,
            password  TEXT    NOT NULL,
            profession        TEXT    NOT NULL,
            profession_group  TEXT    NOT NULL,
            star_color        TEXT
        )
    ''')
    # 如果表已经存在但没有 star_color 列，就添加它
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN star_color TEXT")
    except sqlite3.OperationalError:
        # 已经存在该列时会抛错，忽略即可
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            title           TEXT    NOT NULL,
            content         TEXT    NOT NULL,
            profession_group TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id    INTEGER NOT NULL,
            reactor_id INTEGER NOT NULL,
            type       TEXT    DEFAULT 'resonance',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(post_id)    REFERENCES posts(id),
            FOREIGN KEY(reactor_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
