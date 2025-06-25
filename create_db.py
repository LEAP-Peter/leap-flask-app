import sqlite3

connection = sqlite3.connect("user_data.db")
cursor = connection.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, password TEXT NOT NULL)")


users = [
    ('abc123@example.com', 'abc123'),
    ('abc234@example.com', 'abc234')
]
cursor.executemany("INSERT INTO users (email, password) VALUES (?,?)", users)
connection.commit()
connection.close()