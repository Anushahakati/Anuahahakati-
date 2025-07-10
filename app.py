from flask import Flask, render_template, request, redirect, session, jsonify, url_for, Response
import gspread
import os, json, base64, time, tempfile, shutil
from google.oauth2.service_account import Credentials
from datetime import datetime
from openpyxl import load_workbook
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import numpy as np
import cv2
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

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

# ✅ Google Drive ORB Face Matching Setup
FOLDER_ID = "1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm"
def download_all_drive_images():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.json")
    drive = GoogleDrive(gauth)
    temp_dir = tempfile.mkdtemp()
    query = f"'{FOLDER_ID}' in parents and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()
    for file in file_list:
        if file['title'].endswith('.jpg') or file['title'].endswith('.png'):
            file.GetContentFile(os.path.join(temp_dir, file['title']))
    return temp_dir

def match_faces(live_img, stored_imgs):
    orb = cv2.ORB_create()
    kp1, des1 = orb.detectAndCompute(cv2.cvtColor(live_img, cv2.COLOR_BGR2GRAY), None)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    for file_path, name in stored_imgs:
        img2 = cv2.imread(file_path)
        kp2, des2 = orb.detectAndCompute(cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), None)
        if des1 is not None and des2 is not None:
            matches = bf.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)
            if len(matches) > 15:
                return name
    return None

def gen_frames():
    cap = cv2.VideoCapture(0)
    attendance_taken = set()
    student_dir = download_all_drive_images()
    stored_imgs = [(os.path.join(student_dir, f), f.rsplit('.', 1)[0]) for f in os.listdir(student_dir)]

    while True:
        success, frame = cap.read()
        if not success:
            break

        matched_person = match_faces(frame, stored_imgs)

        if matched_person and matched_person not in attendance_taken:
            mark_attendance_google_sheet(matched_person)
            attendance_taken.add(matched_person)
            cv2.putText(frame, f"{matched_person} - Attendance Taken", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()
    shutil.rmtree(student_dir)

@app.route('/')
def login():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/attendance_status')
def attendance_status():
    return jsonify({"status": "Attendance Taken"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
