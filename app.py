from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import base64, os, json
import cv2
import numpy as np
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# === Google Sheets Setup ===
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds_b64 = os.environ['GOOGLE_CREDS_B64']
creds_json = base64.b64decode(creds_b64).decode('utf-8')
credentials = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key('1WQp2gKH-PpN_YRCXEciqEsDuZITqX3EMA0-oazRcoAs')
sheet = spreadsheet.worksheet("Attendance")

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'bcca' and request.form['password'] == 'bcca':
            session['user'] = 'admin'
            return redirect('/dashboard')
        else:
            return render_template('index.html', error='Invalid Credentials')
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    msg = request.args.get('msg')
    return render_template('dashboard.html', msg=msg)

@app.route('/view-data')
def view_data():
    if 'user' not in session:
        return redirect('/')
    data = sheet.get_all_records()
    return render_template('view_data.html', records=data)

@app.route('/shortage')
def shortage():
    return render_template('shortage.html')

@app.route('/absentees-today')
def absentees_today():
    return render_template('absentees_today.html')

@app.route('/add-student')
def add_student():
    return render_template('add_student.html')

@app.route('/remove-student')
def remove_student():
    return render_template('remove_student.html')

# === Take Attendance Route ===
@app.route('/take-attendance', methods=['POST'])
def take_attendance():
    if 'user' not in session:
        return redirect('/')

    try:
        data = request.get_json()
        image_data = data['image'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # --- Dummy face recognition logic (replace with actual recognition) ---
        student_name = "Anu"
        roll_number = "73"
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        # === Update Google Sheet ===
        sheet.append_row([timestamp, roll_number, student_name, "Present"])

        return jsonify({"message": f"✅ Attendance taken for {student_name} ({roll_number})"})

    except Exception as e:
        print("Error:", e)
        return jsonify({"message": "❌ Failed to take attendance"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
