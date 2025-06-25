from flask import Flask, redirect, url_for, request, render_template, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_s3cr3t_k3y_h3r3'

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        connection = sqlite3.connect("user_data.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        connection.close()
        if user:
            session['email'] = email
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid email or password'
        return f"<h3>Email: {email}<br>Password: {password}</h3>"
    
    return render_template('login.html')

@app.route('/forget')
def forget():
    return "Forget Password Page"  

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/contents')
def contents():
    return render_template('contents.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)