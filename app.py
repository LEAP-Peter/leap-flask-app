from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import os
from jinja2 import TemplateNotFound

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ---- 路径 & 连接 ----
DB_PATH = os.path.join("instance", "user_data.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 支持 dict 风格访问
    return conn

# ---- 数据库初始化（如无则创建）----
def init_db():
    if not os.path.exists("instance"):
        os.makedirs("instance")

    conn = get_connection()
    cur = conn.cursor()

    # users（若你已有此表，字段应尽量一致）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            real_name TEXT,
            username  TEXT,
            email     TEXT UNIQUE,
            password  TEXT,
            profession TEXT,
            profession_group TEXT
        )
    """)

    # posts（包含 title + content）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            profession_group TEXT NOT NULL,
            title   TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # comments
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# 首页 -> 登录
# -------------------------
@app.route("/")
def index():
    return redirect(url_for("login"))

# -------------------------
# 登录
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=? AND password=?", (email, password))
        user = cur.fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# -------------------------
# 注册
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        real_name = request.form["real_name"]
        username  = request.form["username"]
        email     = request.form["email"]
        password  = request.form["password"]
        profession = request.form["profession"]
        profession_group = request.form["profession_group"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (real_name, username, email, password, profession, profession_group) "
            "VALUES (?,?,?,?,?,?)",
            (real_name, username, email, password, profession, profession_group)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("login"))
    return render_template("register.html")

# -------------------------
# 登出
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
# Dashboard（不使用 base.html）
# -------------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE id=?", (session["user_id"],))
    user = cur.fetchone()
    conn.close()

    star_color = "#1b3b6f"
    return render_template("dashboard.html", star_color=star_color, username=user["username"])

# -------------------------
# 用户信息（继承 base.html）
# -------------------------
@app.route("/user_info")
def user_info():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT real_name, username, email, profession, profession_group
        FROM users WHERE id=?
    """, (session["user_id"],))
    user = cur.fetchone()
    conn.close()
    return render_template("user_info.html", user=user)

# -------------------------
# 社区总览（保留 endpoint=community_overview，同时兼容 url_for('communities')）
# -------------------------
@app.route("/community_overview")
@app.route("/communities", endpoint="communities")
def community_overview():
    if "user_id" not in session:
        return redirect(url_for("login"))

    PROFESSION_GROUPS = [
        {"name": "student",   "display": "Student Galaxy"},
        {"name": "engineer",  "display": "Engineer Galaxy"},
        {"name": "artist",    "display": "Artist Galaxy"},
        {"name": "teacher",   "display": "Teacher Galaxy"},
        {"name": "scientist", "display": "Scientist Galaxy"},
        {"name": "other",     "display": "Other Galaxy"},
    ]
    return render_template("community_overview.html", profession_groups=PROFESSION_GROUPS)

# -------------------------
# 社区页：发帖（title+content）+ 列表 + 评论查询
# 优先渲染 galaxies/<group>_galaxy.html，不存在则回退到 community_group.html
# -------------------------
@app.route("/community/<group_name>", methods=["GET", "POST"])
def community_group(group_name):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()

    # 发帖：接收 title + content
    if request.method == "POST" and "content" in request.form:
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            title = "(untitled)"
        if content:  # content 已 required，此判断只是双保险
            cur.execute(
                "INSERT INTO posts (user_id, profession_group, title, content, created_at) "
                "VALUES (?,?,?,?,?)",
                (session["user_id"], group_name, title, content, datetime.now())
            )
            conn.commit()

    # 查询帖子（同时提供 created_at/timestamp 两个键，兼容不同模板）
    cur.execute("""
        SELECT p.id, u.username, p.title, p.content,
               p.created_at AS created_at,
               p.created_at AS timestamp
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.profession_group=?
        ORDER BY p.created_at DESC
    """, (group_name,))
    posts = cur.fetchall()

    # 查询每条帖子的评论
    comments_dict = {}
    for post in posts:
        cur.execute("""
            SELECT c.id, u.username, c.content,
                   c.created_at AS created_at,
                   c.created_at AS timestamp
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id=?
            ORDER BY c.created_at ASC
        """, (post["id"],))
        comments_dict[post["id"]] = cur.fetchall()

    conn.close()

    # 优先渲染单独的 galaxy 模板，不存在则回退到通用模板
    try:
        return render_template(
            f"galaxies/{group_name}_galaxy.html",
            group_name=group_name, posts=posts, comments=comments_dict
        )
    except TemplateNotFound:
        return render_template(
            "community_group.html",
            group_name=group_name, posts=posts, comments=comments_dict
        )

# -------------------------
# 提交评论
# -------------------------
@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    content = (request.form.get("comment_content") or "").strip()
    if not content:
        # 没有内容就直接回帖列表
        # 找到该帖子的所属 group
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT profession_group FROM posts WHERE id=?", (post_id,))
        row = cur.fetchone()
        conn.close()
        group_name = row["profession_group"] if row else "other"
        return redirect(url_for("community_group", group_name=group_name))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?,?,?,?)",
        (post_id, session["user_id"], content, datetime.now())
    )
    conn.commit()

    cur.execute("SELECT profession_group FROM posts WHERE id=?", (post_id,))
    row = cur.fetchone()
    conn.close()
    group_name = row["profession_group"] if row else "other"
    return redirect(url_for("community_group", group_name=group_name))

# -------------------------
# 入口
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
