from flask import Flask, render_template, request, jsonify, session, redirect
import base64
import os
import json
import io
import numpy as np
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from PIL import Image
import cv2

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# === Google Sheets Setup ===
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds_b64 = os.environ.get('GOOGLE_CREDS_B64')
creds_json = base64.b64decode(creds_b64).decode('utf-8')
credentials = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key('1WQp2gKH-PpN_YRCXEciqEsDuZITqX3EMA0-oazRcoAs')
sheet = spreadsheet.worksheet("Attendance")

# === Routes ===

@app.route('/')
def login():
    return redirect('/dashboard')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/take-attendance-page')
def take_attendance_page():
    return render_template('take_attendance.html')

@app.route('/take_attendance', methods=['POST'])
def take_attendance():
    try:
        data = request.get_json()
        image_data = data['image'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # === Save the image for records ===
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs('attendance_images', exist_ok=True)
        save_path = f'attendance_images/face_{timestamp}.jpg'
        cv2.imwrite(save_path, img)

        # === Dummy face recognition result ===
        student_name = "Anu"
        roll_number = "73"

        # === Append to Google Sheet ===
        now = datetime.now()
        sheet.append_row([now.strftime("%Y-%m-%d %H:%M:%S"), roll_number, student_name, "Present"])

        return jsonify({"message": f"✅ Attendance recorded for {student_name} ({roll_number})"})

    except Exception as e:
        print("Error:", e)
        return jsonify({"message": f"❌ Error: {str(e)}"}), 500

# ✅ Additional Routes
@app.route('/view-data')
def view_data():
    return render_template('view_data.html')

@app.route('/shortage')
def shortage():
    return render_template('shortage.html')

@app.route('/absentees_today')
def absentees_today():
    return render_template('absentees_today.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
