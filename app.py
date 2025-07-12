
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import gspread
import os, json, base64, time
from google.oauth2.service_account import Credentials
from datetime import datetime
from openpyxl import load_workbook
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import numpy as np
import cv2

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# === Google Sheets & Drive Setup ===
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

# ✅ Google Sheet Attendance Helper
def mark_attendance_google_sheet(name):
    today = datetime.now().strftime("%Y-%m-%d")
    header = sheet.row_values(1)
    if today in header:
        col = header.index(today) + 1
    else:
        col = len(header) + 1
        sheet.update_cell(1, col, today)

    names = sheet.col_values(1)
    if name in names:
        row = names.index(name) + 1
    else:
        row = len(names) + 1
        sheet.update_cell(row, 1, name)

    sheet.update_cell(row, col, "Present")

# 🧠 Load training images from Google Drive folder (face training)
def load_training_data():
    from googleapiclient.discovery import build
    drive_service = build('drive', 'v3', credentials=credentials)
    folder_id = '1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm'
    results = drive_service.files().list(q=f"'{folder_id}' in parents and mimeType contains 'image'",
                                         fields="files(id, name)").execute()
    files = results.get('files', [])

    face_data = []
    labels = []
    label_map = {}
    count = 0

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    for file in files:
        file_id = file['id']
        file_name = file['name']
        request = drive_service.files().get_media(fileId=file_id)
        fh = open(f"temp_{file_name}", 'wb')
        downloader = MediaFileUpload(fh.name)
        downloader._fd.write(request.execute())
        fh.close()

        img = cv2.imread(fh.name, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        faces = face_cascade.detectMultiScale(img, 1.3, 5)
        for (x, y, w, h) in faces:
            face = img[y:y+h, x:x+w]
            face_data.append(face)
            labels.append(count)
            label_map[count] = os.path.splitext(file_name)[0]
            count += 1
        os.remove(fh.name)

    return face_data, labels, label_map

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
    return render_template('dashboard.html')

@app.route('/live_attendance')
def live_attendance():
    if 'user' not in session:
        return redirect('/')

    face_data, labels, label_map = load_training_data()
    if not face_data:
        return "No training data found."

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(face_data, np.array(labels))

    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    already_detected = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            label, confidence = recognizer.predict(face_roi)

            if confidence < 100:
                name = label_map[label]
                if name not in already_detected:
                    mark_attendance_google_sheet(name)
                    already_detected.add(name)
                    cv2.putText(frame, f"{name} - Attendance Taken", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    time.sleep(2)

        cv2.imshow("Live Attendance", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return redirect('/dashboard')
