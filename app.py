from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DB_PATH = os.path.join('instance', 'user_data.db')

# -------------------------
# 数据库连接
# -------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------
# 初始化数据库（users 表已存在）
# -------------------------
def init_db():
    if not os.path.exists('instance'):
        os.makedirs('instance')
    conn = get_connection()
    cursor = conn.cursor()
    # posts 表: 使用 created_at
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            profession_group TEXT,
            content TEXT,
            created_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    # comments 表: 使用 created_at
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at DATETIME,
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# 启动时初始化数据库
init_db()

# -------------------------
# 首页 -> 登录
# -------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

# -------------------------
# 登录
# -------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

# -------------------------
# 注册
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        real_name = request.form['real_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        profession = request.form['profession']
        profession_group = request.form['profession_group']
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (real_name, username, email, password, profession, profession_group) VALUES (?,?,?,?,?,?)",
            (real_name, username, email, password, profession, profession_group)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# -------------------------
# 登出
# -------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------
# Dashboard
# -------------------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id=?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    star_color = '#1b3b6f'
    return render_template('dashboard.html', star_color=star_color, username=user['username'])

# -------------------------
# 用户信息
# -------------------------
@app.route('/user_info')
def user_info():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT real_name, username, email, profession, profession_group FROM users WHERE id=?",
        (session['user_id'],)
    )
    user = cursor.fetchone()
    conn.close()
    return render_template('user_info.html', user=user)

# -------------------------
# 社区总览
# -------------------------
@app.route('/community_overview')
@app.route('/communities')
def community_overview():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    PROFESSION_GROUPS = [
        {"name": "student", "display": "Student Galaxy"},
        {"name": "engineer", "display": "Engineer Galaxy"},
        {"name": "artist", "display": "Artist Galaxy"},
        {"name": "teacher", "display": "Teacher Galaxy"},
        {"name": "scientist", "display": "Scientist Galaxy"},
        {"name": "other", "display": "Other Galaxy"}
    ]
    return render_template('community_overview.html', profession_groups=PROFESSION_GROUPS)

# -------------------------
# 单个社区 + 发帖 + 评论
# -------------------------
@app.route('/community/<group_name>', methods=['GET', 'POST'])
def community_group(group_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor()
    # 发帖
    if request.method == 'POST' and 'content' in request.form:
        cursor.execute(
            "INSERT INTO posts (user_id, profession_group, content, created_at) VALUES (?,?,?,?)",
            (session['user_id'], group_name, request.form['content'], datetime.now())
        )
        conn.commit()
    # 查询帖子，使用 created_at 并别名 timestamp
    cursor.execute(
        "SELECT p.id, u.username, p.content, p.created_at AS timestamp FROM posts p JOIN users u ON p.user_id=u.id WHERE p.profession_group=? ORDER BY p.created_at DESC",
        (group_name,)
    )
    posts = cursor.fetchall()
    # 查询评论，同样使用 created_at
    comments_dict = {}
    for post in posts:
        cursor.execute(
            "SELECT c.id, u.username, c.content, c.created_at AS timestamp FROM comments c JOIN users u ON c.user_id=u.id WHERE c.post_id=? ORDER BY c.created_at ASC",
            (post['id'],)
        )
        comments_dict[post['id']] = cursor.fetchall()
    conn.close()
    return render_template(f'galaxies/{group_name}_galaxy.html', posts=posts, comments=comments_dict, group_name=group_name)

# -------------------------
# 评论提交
# -------------------------
@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?,?,?,?)",
        (post_id, session['user_id'], request.form['comment_content'], datetime.now())
    )
    conn.commit()
    # 获取 profession_group
    cursor.execute("SELECT profession_group FROM posts WHERE id=?", (post_id,))
    group_name = cursor.fetchone()['profession_group']
    conn.close()
    return redirect(url_for('community_group', group_name=group_name))

if __name__ == '__main__':
    app.run(debug=True)
