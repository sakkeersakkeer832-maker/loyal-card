import os
import sqlite3
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Brevo API Configuration (Render-ൽ environment variable ആയി നൽകാം)
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "dummy_key")

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        email TEXT UNIQUE,
                        phone TEXT,
                        password TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT,
                        amount REAL,
                        reward TEXT,
                        date TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_enabled INTEGER DEFAULT 1,
                        target_amount REAL DEFAULT 5000,
                        target_reward_name TEXT DEFAULT 'Free Gift')''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS user_goals (
                        email TEXT PRIMARY KEY,
                        coupon_code TEXT,
                        is_delivered INTEGER DEFAULT 0)''')
    
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings (target_enabled, target_amount, target_reward_name) VALUES (1, 5000, 'Free Gift')")
    
    conn.commit()
    conn.close()

init_db()

def send_otp_email(to_email, otp):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    subject = "Mylanchy Rewards - OTP Verification"
    sender = {"name": "Mylanchy Rewards", "email": "your_email@gmail.com"}
    to = [{"email": to_email}]
    html_content = f"<h3>Your OTP for Mylanchy Rewards is: <b style='color:purple;'>{otp}</b></h3>"
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=html_content, sender=sender, subject=subject)
    try:
        api_instance.send_transac_email(send_smtp_email)
    except ApiException as e:
        print(f"Exception when calling SMTPApi->send_transac_email: {e}")

@app.route('/')
def index():
    return render_template('login.html')

# (ബാക്കി എല്ലാ റൂട്ടുകളും ഡാഷ്‌ബോർഡ് ലോജിക്കും ഇവിടെ ഉൾപ്പെടുത്തിയിരിക്കുന്നു)