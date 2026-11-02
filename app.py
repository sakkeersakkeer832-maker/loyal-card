from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import random
import requests
import os

app = Flask(__name__)
app.secret_key = "mylanchy_super_secret_key"

app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Brevo API Configuration (Environment variable വഴി സുരക്ഷിതമായി എടുക്കും)
# Brevo API Configuration
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "dummy_key")
SENDER_EMAIL = "sakkeersakkeer832@gmail.com"

def send_email_otp(to_email, otp):
    print("==================================================")
    print(f"👉 DEBUG OTP FOR {to_email}: {otp}")
    print("==================================================")
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        payload = {
            "sender": {
                "name": "Mylanchy Rewards",
                "email": SENDER_EMAIL
            },
            "to": [
                {
                    "email": to_email
                }
            ],
            "subject": "Mylanchy Rewards OTP Code",
            "textContent": f"Your Mylanchy Rewards verification code is: {otp}"
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            print("Email sent successfully via Brevo API!")
        else:
            print("Brevo Error Response:", response.text)
    except Exception as e:
        print("Email sending error:", e)

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, coupon_code TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, amount REAL, reward TEXT DEFAULT 'Pending', timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS shop_settings 
                      (id INTEGER PRIMARY KEY, target_amount REAL DEFAULT 5000, target_enabled INTEGER DEFAULT 1, target_reward_name TEXT DEFAULT 'Surprise Gift')''')
    
    try:
        cursor.execute("ALTER TABLE shop_settings ADD COLUMN target_reward_name TEXT DEFAULT 'Surprise Gift'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE shop_settings ADD COLUMN target_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN coupon_code TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
        
    cursor.execute("INSERT OR IGNORE INTO shop_settings (id, target_amount, target_enabled, target_reward_name) VALUES (1, 5000, 1, 'Surprise Gift')")
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].strip().lower()
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        conn.close()
        
        if existing_user:
            return render_template('register.html', error="Email already registered! Please Login.")
        
        otp = str(random.randint(1000, 9999))
        session['temp_user'] = {'name': name, 'email': email, 'otp': otp}
        send_email_otp(email, otp) 
        
        return redirect(url_for('verify_otp'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return render_template('login.html', error="Email not found! Please Register first.")
            
        otp = str(random.randint(1000, 9999))
        session['temp_user'] = {'name': user[1], 'email': email, 'otp': otp}
        send_email_otp(email, otp)
        
        return redirect(url_for('verify_otp'))
        
    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify_otp():
    temp_user = session.get('temp_user')
    if not temp_user:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        
        if entered_otp == temp_user.get('otp'):
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (name, email) VALUES (?, ?)", 
                           (temp_user['name'], temp_user['email']))
            conn.commit()
            conn.close()
            
            session['authenticated_user'] = temp_user['email']
            session.pop('temp_user', None)
            return redirect(url_for('dashboard'))
        else:
            return render_template('verify_otp.html', error="Invalid OTP! Try Again.")
            
    return render_template('verify_otp.html')

@app.route('/resend_otp', methods=['GET', 'POST'])
def resend_otp():
    temp_user = session.get('temp_user')
    if not temp_user:
        return redirect(url_for('index'))
    
    otp = str(random.randint(1000, 9999))
    temp_user['otp'] = otp
    session['temp_user'] = temp_user
    send_email_otp(temp_user['email'], otp)
    
    return render_template('verify_otp.html', msg="A new OTP has been sent to your email!")

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    email = session.get('authenticated_user')
    if not email:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        cursor.execute("INSERT INTO transactions (email, amount, timestamp) VALUES (?, ?, datetime('now', 'localtime'))", (email, amount))
        conn.commit()
        
        cursor.execute("SELECT target_amount, target_enabled FROM shop_settings WHERE id = 1")
        st = cursor.fetchone()
        t_amt = st[0] if st else 5000.0
        t_enabled = st[1] if st else 1
        
        generated_coupon = ""
        if t_enabled == 1:
            cursor.execute("SELECT SUM(amount) FROM transactions WHERE email = ?", (email,))
            tot = cursor.fetchone()
            spent = tot[0] if tot and tot[0] else 0.0
            
            if spent >= t_amt:
                cursor.execute("SELECT coupon_code FROM users WHERE email = ?", (email,))
                usr = cursor.fetchone()
                if usr and usr[0]:
                    generated_coupon = usr[0]
                else:
                    generated_coupon = f"MYLANCHY-{random.randint(1000, 9999)}"
                    cursor.execute("UPDATE users SET coupon_code = ? WHERE email = ?", (generated_coupon, email))
                    conn.commit()

        conn.close()
        return {"status": "success", "coupon": generated_coupon}, 200
    
    cursor.execute("SELECT name, coupon_code FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    user_name = user[0] if user else "Customer"
    coupon_code = user[1] if user else ""
    
    cursor.execute("SELECT target_amount, target_enabled, target_reward_name FROM shop_settings WHERE id = 1")
    setting = cursor.fetchone()
    target_amount = setting[0] if setting else 5000.0
    target_enabled = setting[1] if setting is not None else 1
    target_reward_name = setting[2] if setting else "Surprise Gift"
    
    total_spent = 0.0
    if target_enabled == 1:
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE email = ?", (email,))
        total_spent_res = cursor.fetchone()
        total_spent = total_spent_res[0] if total_spent_res and total_spent_res[0] else 0.0
        
        if total_spent >= target_amount and not coupon_code:
            coupon_code = f"MYLANCHY-{random.randint(1000, 9999)}"
            cursor.execute("UPDATE users SET coupon_code = ? WHERE email = ?", (coupon_code, email))
            conn.commit()
    
    cursor.execute("SELECT id, amount, reward, timestamp FROM transactions WHERE email = ? ORDER BY id DESC", (email,))
    transactions = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', user_name=user_name, transactions=transactions, 
                           total_spent=total_spent, target_amount=target_amount, 
                           target_enabled=target_enabled, target_reward_name=target_reward_name,
                           coupon_code=coupon_code)

@app.route('/delete_txn/<int:txn_id>', methods=['POST'])
def delete_txn(txn_id):
    email = session.get('authenticated_user')
    if not email:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ? AND email = ? AND reward = 'Pending'", (txn_id, email))
    conn.commit()
    conn.close()
    return "Deleted", 200

@app.route('/logout')
def logout():
    session.pop('authenticated_user', None)
    return redirect(url_for('index'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == "admin" and password == "mylanchy123":
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin_login.html', error="Invalid Username or Password!")
            
    return render_template('admin_login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    if request.method == 'POST':
        if 'target_amount' in request.form:
            new_target = request.form['target_amount']
            target_enabled = 1 if 'target_enabled' in request.form else 0
            target_reward_name = request.form['target_reward_name']
            
            cursor.execute("UPDATE shop_settings SET target_amount = ?, target_enabled = ?, target_reward_name = ? WHERE id = 1", (new_target, target_enabled, target_reward_name))
            conn.commit()
        elif 'complete_goal_email' in request.form:
            c_email = request.form['complete_goal_email']
            
            cursor.execute("SELECT target_amount FROM shop_settings WHERE id = 1")
            st = cursor.fetchone()
            t_amt = st[0] if st else 5000.0
            
            cursor.execute("SELECT SUM(amount) FROM transactions WHERE email = ?", (c_email,))
            tot = cursor.fetchone()
            total_spent = tot[0] if tot and tot[0] else 0.0
            
            balance_amount = total_spent - t_amt
            if balance_amount < 0:
                balance_amount = 0.0
            
            cursor.execute("DELETE FROM transactions WHERE email = ?", (c_email,))
            
            if balance_amount > 0:
                cursor.execute("INSERT INTO transactions (email, amount, reward, timestamp) VALUES (?, ?, 'Approved', datetime('now', 'localtime'))", (c_email, balance_amount))
            
            cursor.execute("UPDATE users SET coupon_code = '' WHERE email = ?", (c_email,))
            conn.commit()
            
        elif 'txn_id' in request.form:
            txn_id = request.form['txn_id']
            reward = request.form['reward']
            cursor.execute("UPDATE transactions SET reward = ? WHERE id = ?", (reward, txn_id))
            conn.commit()
        
    cursor.execute("SELECT target_amount, target_enabled, target_reward_name FROM shop_settings WHERE id = 1")
    setting = cursor.fetchone()
    target_amount = setting[0] if setting else 5000.0
    target_enabled = setting[1] if setting is not None else 1
    target_reward_name = setting[2] if setting else "Surprise Gift"

    cursor.execute("SELECT transactions.id, users.name, transactions.email, transactions.amount, transactions.reward FROM transactions JOIN users ON transactions.email = users.email ORDER BY transactions.id DESC")
    requests_list = cursor.fetchall()
    
    cursor.execute("SELECT u.name, u.email, SUM(t.amount) as total, u.coupon_code FROM users u JOIN transactions t ON u.email = t.email GROUP BY u.email HAVING total >= ? AND u.coupon_code != ''", (target_amount,))
    target_reached_users = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin.html', requests=requests_list, target_amount=target_amount, 
                           target_enabled=target_enabled, target_reward_name=target_reward_name, 
                           target_reached_users=target_reached_users)

@app.route('/admin/delete_txn/<int:txn_id>', methods=['POST'])
def admin_delete_txn(txn_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    conn.commit()
    conn.close()
    return "Deleted", 200

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)