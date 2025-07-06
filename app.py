from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import subprocess
import gspread
import os, json, base64
from google.oauth2.service_account import Credentials
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
from openpyxl import load_workbook, Workbook

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

# === Known Faces Setup (using OpenCV LBPH) ===
recognizer = cv2.face.LBPHFaceRecognizer_create()
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

data_dir = "data"
label_map = {}
x_train, y_labels = [], []
label_id = 0

for filename in os.listdir(data_dir):
    if filename.endswith(".png") or filename.endswith(".jpg"):
        path = os.path.join(data_dir, filename)
        label = filename.rsplit(".", 1)[0]
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        faces = face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5)
        for (x, y, w, h) in faces:
            roi = img[y:y + h, x:x + w]
            x_train.append(roi)
            y_labels.append(label_id)
        label_map[label_id] = label
        label_id += 1

if x_train:
    recognizer.train(x_train, np.array(y_labels))

# === Attendance Helper ===
def update_google_sheet(sheet, date_header, name):
    headers = sheet.row_values(1)
    if not headers or headers[0] != "Name":
        sheet.update_cell(1, 1, "Name")
        headers = ["Name"] + headers

    if name not in sheet.col_values(1):
        sheet.append_row([name])

    if date_header not in headers:
        sheet.update_cell(1, len(headers) + 1, date_header)
        headers.append(date_header)

    col_index = headers.index(date_header) + 1
    records = sheet.get_all_values()
    for idx, row in enumerate(records):
        if row[0] == name:
            sheet.update_cell(idx + 1, col_index, "Present")
        elif len(row) < col_index or not row[col_index - 1]:
            sheet.update_cell(idx + 1, col_index, "Absent")

def update_excel(date_header, name):
    EXCEL_PATH = "attend.xlsx"
    try:
        if os.path.exists(EXCEL_PATH):
            wb = load_workbook(EXCEL_PATH)
            ws = wb.active
        else:
            wb = Workbook()
            ws = wb.active
            ws.cell(row=1, column=1, value="Name")

        names = [ws.cell(row=i, column=1).value for i in range(2, ws.max_row + 1)]
        if name not in names:
            ws.append([name])

        headers = [ws.cell(row=1, column=j).value for j in range(1, ws.max_column + 1)]
        if date_header not in headers:
            col_index = len(headers) + 1
            ws.cell(row=1, column=col_index, value=date_header)
        else:
            col_index = headers.index(date_header) + 1

        for i in range(2, ws.max_row + 1):
            student = ws.cell(row=i, column=1).value
            current = ws.cell(row=i, column=col_index).value
            if student == name:
                ws.cell(row=i, column=col_index, value="Present")
            elif not current:
                ws.cell(row=i, column=col_index, value="Absent")

        wb.save(EXCEL_PATH)
    except Exception as e:
        print("Excel update error:", e)

@app.route('/')
def home():
    return "Hello from Flask + OpenCV!"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'bcca' and request.form['password'] == 'bcca':
            session['user'] = 'admin'
            return redirect('/dashboard')
        return render_template('index.html', error='Invalid Credentials')
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html')

@app.route('/take_attendance', methods=['POST'])
def take_attendance():
    if 'user' not in session:
        return redirect('/')
    try:
        data = request.get_json()
        image_data = data['image'].split(',')[1]
        img_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(img_bytes)).convert('L')
        frame = np.array(img)
        faces = face_cascade.detectMultiScale(frame, scaleFactor=1.1, minNeighbors=5)

        recognized_names = set()
        for (x, y, w, h) in faces:
            roi = frame[y:y + h, x:x + w]
            label_id_pred, confidence = recognizer.predict(roi)
            if confidence < 70:
                recognized_names.add(label_map[label_id_pred])

        if recognized_names:
            date_header = datetime.now().strftime("%Y-%m-%d")
            for name in recognized_names:
                update_google_sheet(sheet, date_header, name)
                update_excel(date_header, name)
            return jsonify({"message": f"✅ Attendance taken for: {', '.join(recognized_names)}"})
        return jsonify({"message": "❌ No known faces recognized!"})
    except Exception as e:
        return jsonify({"message": f"❌ Error: {str(e)}"}), 500

@app.route('/view_data')
def view_data():
    if 'user' not in session:
        return redirect('/')
    return render_template('view_data.html', records=sheet.get_all_values())

@app.route('/shortage')
def shortage():
    if 'user' not in session:
        return redirect('/')
    records = sheet.get_all_values()
    headers = records[0][1:]
    result = []
    for row in records[1:]:
        present = row[1:].count("Present")
        if present < 0.75 * len(headers):
            result.append([row[0], present, len(headers)])
    return render_template('shortage.html', result=result)

@app.route('/absentees_today')
def absentees_today():
    if 'user' not in session:
        return redirect('/')
    today = datetime.now().strftime('%Y-%m-%d')
    records = sheet.get_all_records()
    absentees = [r['Name'] for r in records if r.get(today) == 'Absent']
    return render_template('absentees.html', absentees=absentees, date=today)

@app.route('/add-student', methods=['GET', 'POST'])
def add_student():
    if 'user' not in session:
        return redirect('/')
    if request.method == 'POST':
        name = request.form['name']
        photo_data = request.form['photo']
        try:
            _, encoded = photo_data.split(",")
            image_bytes = base64.b64decode(encoded)
            filename = f"{name}.png"
            os.makedirs("data", exist_ok=True)
            with open(os.path.join("data", filename), "wb") as f:
                f.write(image_bytes)
            upload_to_drive(os.path.join("data", filename), filename, '146S39x63_ycnNpv9vgtLOE18cx-54ghG')
        except Exception as e:
            return f"Error processing image: {e}", 400

        try:
            existing = sheet.get_all_values()
            sheet.append_row([name] + [''] * (len(existing[0]) - 1))
        except Exception as e:
            return f"Sheet error: {e}", 500

        return render_template('dashboard.html', msg="Student added successfully")
    return render_template('add_student.html')

@app.route('/remove-student', methods=['GET', 'POST'])
def remove_student():
    if 'user' not in session:
        return redirect('/')
    names = [row[0] for row in sheet.get_all_values()[1:]]
    if request.method == 'POST':
        name = request.form['name']
        for i, row in enumerate(sheet.get_all_values()):
            if row[0] == name:
                sheet.delete_rows(i + 1)
                break
        return render_template('remove_student.html', students=[row[0] for row in sheet.get_all_values()[1:]], msg=f"{name} removed.")
    return render_template('remove_student.html', students=names)

def upload_to_drive(file_path, file_name, folder_id):
    drive_service = build('drive', 'v3', credentials=credentials)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/png')
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded.get('id')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
