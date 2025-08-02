import os
import random
from flask import Flask, render_template, request, redirect, session, url_for, flash
from models import create_tables, get_connection

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

INSTANCE_DIR = os.path.join(os.getcwd(), 'instance')
if not os.path.exists(INSTANCE_DIR):
    os.makedirs(INSTANCE_DIR)

PROFESSION_GROUPS = [
    "student", "engineer", "artist", "teacher", "scientist", "other"
]

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        real_name       = request.form['real_name']
        username        = request.form['username']
        email           = request.form['email']
        password        = request.form['password']
        profession      = request.form['profession']
        profession_group= request.form['profession_group']

        # 生成一次性随机星星，仅注册时生成一次
        star_color = "#{:02X}{:02X}{:02X}".format(
            random.randint(200,255),
            random.randint(150,220),
            random.randint( 50,100)
        )

        conn = get_connection()
        cursor = conn.cursor()
        # 检查邮箱或用户名重复
        cursor.execute("SELECT 1 FROM users WHERE email=? OR username=?", (email, username))
        if cursor.fetchone():
            conn.close()
            return "<h3>Email or username already registered. Please try another.</h3><a href='/register'>Back</a>"

        # 插入新用户，并保存 star_color
        cursor.execute('''
            INSERT INTO users
                (real_name, username, email, password, profession, profession_group, star_color)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (real_name, username, email, password, profession, profession_group, star_color))
        conn.commit()
        conn.close()

        return render_template('register_success.html')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id']  = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password."

    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_connection()
    cursor = conn.cursor()

    # 读取用户基本信息 + 固定星星颜色（不再随机）
    cursor.execute(
        "SELECT username, profession_group, star_color FROM users WHERE id=?",
        (user_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "<h3>User not found.</h3>"

    username, profession_group, star_color = row

    # 查询同星系其他成员
    cursor.execute(
        "SELECT real_name, profession FROM users WHERE profession_group=? AND id<>?",
        (profession_group, user_id)
    )
    group_users = cursor.fetchall()
    conn.close()

    group_list = [
        {'real_name': u['real_name'], 'profession': u['profession']}
        for u in group_users
    ]

    return render_template(
        'dashboard.html',
        username=username,
        profession_group=profession_group,
        star_color=star_color,
        group_users=group_list
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/user_info', methods=['GET', 'POST'])
def user_info():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        real_name       = request.form['real_name']
        username        = request.form['username']
        profession      = request.form['profession']
        profession_group= request.form['profession_group']
        star_color      = request.form['star_color']

        cursor.execute('''
            UPDATE users
               SET real_name=?,
                   username=?,
                   profession=?,
                   profession_group=?,
                   star_color=?
             WHERE id=?
        ''', (real_name, username, profession, profession_group, star_color, user_id))
        conn.commit()
        flash("Your profile has been updated.", "success")

    cursor.execute('''
        SELECT real_name, username, email, profession, profession_group, star_color
          FROM users
         WHERE id=?
    ''', (user_id,))
    user = cursor.fetchone()
    conn.close()

    return render_template('user_info.html', user=user)

@app.route('/community_overview')
def community_overview():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('community_overview.html', profession_groups=PROFESSION_GROUPS)

@app.route('/community/<group_name>')
def community_group(group_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if group_name not in PROFESSION_GROUPS:
        return "<h3>Community not found.</h3>"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.title, u.username, p.created_at
          FROM posts p
          JOIN users u ON p.user_id = u.id
         WHERE p.profession_group=?
         ORDER BY p.created_at DESC
    ''', (group_name,))
    posts = cursor.fetchall()
    conn.close()

    return render_template(
        'community_group.html',
        group_name=group_name,
        posts=posts
    )

if __name__ == '__main__':
    app.run(debug=True)