from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import gspread
import os, json, base64, time, io
from google.oauth2.service_account import Credentials
from datetime import datetime
from openpyxl import load_workbook
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import numpy as np
import cv2

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

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

def download_known_faces(folder_id):
    drive_service = build('drive', 'v3', credentials=credentials)
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png')",
        fields="files(id, name)").execute()
    files = results.get('files', [])
    os.makedirs("known_faces", exist_ok=True)
    known_images = []
    known_labels = []

    for file in files:
        file_id = file['id']
        file_name = file['name']
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        img_array = np.asarray(bytearray(fh.read()), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is not None:
            known_images.append(img)
            known_labels.append(os.path.splitext(file_name)[0])

    return known_images, known_labels

def recognize_person(face_img, known_images, known_labels):
    face_gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    face_hist = cv2.calcHist([face_gray], [0], None, [256], [0, 256])
    face_hist = cv2.normalize(face_hist, face_hist).flatten()
    best_match = None
    best_score = 0.7
    for known_img, label in zip(known_images, known_labels):
        known_gray = cv2.cvtColor(known_img, cv2.COLOR_BGR2GRAY)
        known_hist = cv2.calcHist([known_gray], [0], None, [256], [0, 256])
        known_hist = cv2.normalize(known_hist, known_hist).flatten()
        score = cv2.compareHist(face_hist, known_hist, cv2.HISTCMP_CORREL)
        if score > best_score:
            best_score = score
            best_match = label
    return best_match

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

    known_images, known_labels = download_known_faces('1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm')
    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    detected_set = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face_crop = frame[y:y+h, x:x+w]
            identity = recognize_person(face_crop, known_images, known_labels)
            if identity and identity not in detected_set:
                detected_set.add(identity)
                mark_attendance_google_sheet(identity)
                cv2.putText(frame, f"{identity} - Attendance Taken", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                print(f"✅ Attendance taken for {identity}")
                time.sleep(2)

        cv2.imshow("Live Attendance", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return redirect('/dashboard')

# (All your other routes remain unchanged...)
# take_attendance, view_data, shortage, absentees_today, add_student, remove_student, upload_to_drive

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
