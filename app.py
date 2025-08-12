from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from sqlite3 import OperationalError
from datetime import datetime
import os
from jinja2 import TemplateNotFound

app = Flask(__name__)
app.secret_key = "your_secret_key"

DB_PATH = os.path.join("instance", "user_data.db")


# -------------------------
# DB helpers
# -------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict 风格访问
    return conn


def table_has_column(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def init_db():
    """初次创建表（如不存在）"""
    if not os.path.exists("instance"):
        os.makedirs("instance")

    conn = get_connection()
    cur = conn.cursor()

    # users（如果你已有此表，字段尽量兼容）
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            real_name TEXT,
            username  TEXT,
            email     TEXT UNIQUE,
            password  TEXT,
            profession TEXT,
            profession_group TEXT
        )
        """
    )

    # posts：带 title 与 created_at（旧库可能没有）
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            profession_group TEXT NOT NULL,
            title   TEXT,
            content TEXT,
            created_at DATETIME,
            timestamp DATETIME,    -- 兼容旧库（可为空）
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # comments：created_at/timestamp 二选一
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT,
            created_at DATETIME,
            timestamp DATETIME,    -- 兼容旧库（可为空）
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()


def migrate_schema():
    """运行期迁移：如缺少列则补齐"""
    conn = get_connection()
    cur = conn.cursor()

    # posts
    if not table_has_column(conn, "posts", "title"):
        cur.execute("ALTER TABLE posts ADD COLUMN title TEXT DEFAULT '(untitled)'")
    if not table_has_column(conn, "posts", "content"):
        cur.execute("ALTER TABLE posts ADD COLUMN content TEXT")
    if not table_has_column(conn, "posts", "created_at"):
        cur.execute("ALTER TABLE posts ADD COLUMN created_at DATETIME")
    # 某些旧库只有 timestamp，这里不删，仅作兼容
    if not table_has_column(conn, "posts", "timestamp"):
        cur.execute("ALTER TABLE posts ADD COLUMN timestamp DATETIME")

    # comments
    if not table_has_column(conn, "comments", "created_at"):
        cur.execute("ALTER TABLE comments ADD COLUMN created_at DATETIME")
    if not table_has_column(conn, "comments", "timestamp"):
        cur.execute("ALTER TABLE comments ADD COLUMN timestamp DATETIME")

    conn.commit()
    conn.close()


# 初始化 & 迁移
init_db()
migrate_schema()


# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
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


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        real_name = request.form["real_name"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        profession = request.form["profession"]
        profession_group = request.form["profession_group"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (real_name, username, email, password, profession, profession_group) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (real_name, username, email, password, profession, profession_group),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


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


@app.route("/user_info")
def user_info():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT real_name, username, email, profession, profession_group FROM users WHERE id=?",
        (session["user_id"],),
    )
    user = cur.fetchone()
    conn.close()
    return render_template("user_info.html", user=user)


# 保留 community_overview，同时提供 'communities' 别名，兼容模板中的 url_for('communities')
@app.route("/community_overview")
@app.route("/communities", endpoint="communities")
def community_overview():
    if "user_id" not in session:
        return redirect(url_for("login"))

    PROFESSION_GROUPS = [
        {"name": "student", "display": "Student Galaxy"},
        {"name": "engineer", "display": "Engineer Galaxy"},
        {"name": "artist", "display": "Artist Galaxy"},
        {"name": "teacher", "display": "Teacher Galaxy"},
        {"name": "scientist", "display": "Scientist Galaxy"},
        {"name": "other", "display": "Other Galaxy"},
    ]
    return render_template("community_overview.html", profession_groups=PROFESSION_GROUPS)


@app.route("/community/<group_name>", methods=["GET", "POST"])
def community_group(group_name):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()

    # 发帖：title + content
    if request.method == "POST" and "content" in request.form:
        title = (request.form.get("title") or "").strip() or "(untitled)"
        content = (request.form.get("content") or "").strip()
        if content:
            # 优先写 created_at 列；旧库只有 timestamp 时回退
            try:
                cur.execute(
                    "INSERT INTO posts (user_id, profession_group, title, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (session["user_id"], group_name, title, content, datetime.now()),
                )
            except OperationalError:
                cur.execute(
                    "INSERT INTO posts (user_id, profession_group, title, content, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (session["user_id"], group_name, title, content, datetime.now()),
                )
            conn.commit()

    # 查询帖子（使用 COALESCE 兼容 created_at/timestamp）
    cur.execute(
        """
        SELECT p.id, u.username, p.title, p.content,
               COALESCE(p.created_at, p.timestamp) AS created_at,
               COALESCE(p.created_at, p.timestamp) AS timestamp
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.profession_group=?
        ORDER BY COALESCE(p.created_at, p.timestamp) DESC
        """,
        (group_name,),
    )
    posts = cur.fetchall()

    # 查询每条帖子的评论（同样 COALESCE）
    comments_dict = {}
    for post in posts:
        cur.execute(
            """
            SELECT c.id, u.username, c.content,
                   COALESCE(c.created_at, c.timestamp) AS created_at,
                   COALESCE(c.created_at, c.timestamp) AS timestamp
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id=?
            ORDER BY COALESCE(c.created_at, c.timestamp) ASC
            """,
            (post["id"],),
        )
        comments_dict[post["id"]] = cur.fetchall()

    conn.close()

    # 优先渲染独立 galaxy 模板，不存在则回退通用模板
    try:
        return render_template(
            f"galaxies/{group_name}_galaxy.html",
            group_name=group_name,
            posts=posts,
            comments=comments_dict,
        )
    except TemplateNotFound:
        return render_template(
            "community_group.html",
            group_name=group_name,
            posts=posts,
            comments=comments_dict,
        )


@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    content = (request.form.get("comment_content") or "").strip()
    if not content:
        # 没内容直接回到所在群组
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT profession_group FROM posts WHERE id=?", (post_id,))
        row = cur.fetchone()
        conn.close()
        group_name = row["profession_group"] if row else "other"
        return redirect(url_for("community_group", group_name=group_name))

    conn = get_connection()
    cur = conn.cursor()
    # 优先写 created_at；旧库回退写 timestamp
    try:
        cur.execute(
            "INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
            (post_id, session["user_id"], content, datetime.now()),
        )
    except OperationalError:
        cur.execute(
            "INSERT INTO comments (post_id, user_id, content, timestamp) VALUES (?, ?, ?, ?)",
            (post_id, session["user_id"], content, datetime.now()),
        )
    conn.commit()

    cur.execute("SELECT profession_group FROM posts WHERE id=?", (post_id,))
    row = cur.fetchone()
    conn.close()
    group_name = row["profession_group"] if row else "other"
    return redirect(url_for("community_group", group_name=group_name))


if __name__ == "__main__":
    app.run(debug=True)
