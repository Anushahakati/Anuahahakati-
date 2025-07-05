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

@app.route('/view-data')
def view_data():
    return render_template('view_data.html')

@app.route('/shortage')
def shortage():
    return render_template('shortage.html')

@app.route('/absentees_today')
def absentees_today():
    return render_template('absentees_today.html')

@app.route('/add-student')
def add_student():
    return render_template('add_student.html')

@app.route('/remove-student', methods=['GET', 'POST'])
def remove_student():
    students = sheet.col_values(3)[1:]  # assuming column 3 has student names, skip header
    if request.method == 'POST':
        name_to_remove = request.form.get('name')
        all_data = sheet.get_all_values()

        for i, row in enumerate(all_data):
            if len(row) >= 3 and row[2] == name_to_remove:
                sheet.delete_rows(i + 1)
                break
        return render_template('remove_student.html', students=sheet.col_values(3)[1:], msg=f"{name_to_remove} removed.")

    return render_template('remove_student.html', students=students)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
