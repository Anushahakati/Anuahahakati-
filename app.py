from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import subprocess
import gspread
import os, json, base64, time
from google.oauth2.service_account import Credentials
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import numpy as np
import cv2
import face_recognition
from openpyxl import load_workbook

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_b64 = os.environ.get('GOOGLE_CREDS_B64')
creds_json = base64.b64decode(creds_b64).decode('utf-8')
credentials = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key('1WQp2gKH-PpN_YRCXEciqEsDuZITqX3EMA0-oazRcoAs')
sheet = spreadsheet.worksheet("Attendance")

# === Routes ===

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

@app.route('/run_attendance')
def run_attendance():
    if 'user' not in session:
        return redirect('/')

    inp = 'CS101'  # Replace with your method to get input
    wb_path = 'attend.xlsx'
    rb = load_workbook(wb_path)

    if inp in rb.sheetnames:
        sheetx = rb[inp]
        sheetx.cell(row=1, column=1, value='Name-Rollno')
        column_number = sheetx.max_column + 1
    else:
        sheetx = rb.create_sheet(inp)
        sheetx.cell(row=1, column=1, value='Name-Rollno')
        column_number = 2

    attendance_time = datetime.now().strftime("%m/%d/%Y")
    sheetx.cell(row=1, column=column_number, value=attendance_time)

    fixed_start = datetime.now().replace(hour=14, minute=21, second=0, microsecond=0)
    already_attendance_taken = set()

    while datetime.now() < fixed_start:
        time.sleep(1)

    TIME_LIMIT_SECONDS = 5
    start_time = time.time()

    known_face_encodings = []
    known_face_names = []
    folder = 'data'
    for filename in os.listdir(folder):
        if filename.endswith('.png'):
            path = os.path.join(folder, filename)
            img = face_recognition.load_image_file(path)
            encodings = face_recognition.face_encodings(img)
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_names.append(filename.rsplit('.', 1)[0])

    capture = cv2.VideoCapture(0)
    process_this_frame = True

    while True:
        if time.time() - start_time > TIME_LIMIT_SECONDS:
            break

        ret, frame = capture.read()
        if not ret:
            break

        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = small_frame[:, :, ::-1]

        if process_this_frame:
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            face_names = []
            for face_encoding in face_encodings:
                name = "Unknown"
                distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                if distances.size:
                    min_index = np.argmin(distances)
                    if distances[min_index] < 0.5:
                        name = known_face_names[min_index]

                face_names.append(name)
                if name != "Unknown" and name not in already_attendance_taken:
                    name_exists = False
                    for cell in sheetx["A"]:
                        if cell.value == name:
                            name_exists = True
                            row = cell.row
                            break
                    if name_exists:
                        sheetx.cell(row=row, column=column_number, value="Present")
                    else:
                        row = sheetx.max_row + 1
                        sheetx.cell(row=row, column=1, value=name)
                        sheetx.cell(row=row, column=column_number, value="Present")
                    already_attendance_taken.add(name)
                    rb.save(wb_path)

        process_this_frame = not process_this_frame

        for (top, right, bottom, left), name in zip(face_locations, face_names):
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

        cv2.imshow('Webcam', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    capture.release()
    cv2.destroyAllWindows()
    return render_template('dashboard.html', msg="✅ Attendance finished")

# === Start Server ===

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
