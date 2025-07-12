
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

    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    already_detected = set()

    os.makedirs("attendance_images", exist_ok=True)
    print("🔄 Starting Live Attendance...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face_id = f"{x}_{y}_{w}_{h}"
            if face_id not in already_detected:
                name = f"person_{datetime.now().strftime('%H%M%S')}"
                image_path = os.path.join("attendance_images", f"{name}.png")
                cv2.imwrite(image_path, frame)

                mark_attendance_google_sheet(name)
                already_detected.add(face_id)

                try:
                    upload_to_drive(image_path, f"{name}.png", '1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm')
                except Exception as e:
                    print("Drive upload failed:", e)

                cv2.putText(frame, f"{name} - Attendance Taken", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                time.sleep(2)

        cv2.imshow("Live Attendance", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("📴 Attendance stopped by user.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return redirect('/dashboard')

# ✅ NEW: Web Camera Attendance Capture
@app.route('/take_attendance', methods=['POST'])
def take_attendance():
    if 'user' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        image_data = data.get('image')
        if not image_data:
            print("No image data received.")
            return jsonify({'message': 'No image received'}), 400

        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Face detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) == 0:
            return jsonify({'message': 'No face detected'}), 400

        name = "Person_" + datetime.now().strftime('%H%M%S')
        mark_attendance_google_sheet(name)

        os.makedirs("attendance_images", exist_ok=True)
        filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = os.path.join("attendance_images", filename)
        cv2.imwrite(save_path, img)

        upload_to_drive(save_path, filename, '1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm')

        return jsonify({'message': f'✅ Attendance taken for {name}'})
    
    except Exception as e:
        print("Error in /take_attendance:", e)
        return jsonify({'message': 'Something went wrong.'}), 500

@app.route('/view_data')
def view_data():
    if 'user' not in session:
        return redirect('/')
    records = sheet.get_all_values()
    return render_template('view_data.html', records=records)

@app.route('/shortage')
def shortage():
    if 'user' not in session:
        return redirect('/')
    records = sheet.get_all_values()
    headers = records[0][1:]
    result = []
    for row in records[1:]:
        present_count = row[1:].count('Present')
        if present_count < len(headers) * 0.75:
            result.append([row[0], present_count, len(headers)])
    return render_template('shortage.html', result=result)

@app.route('/absentees_today')
def absentees_today():
    if 'user' not in session:
        return redirect('/')
    try:
        all_data = sheet.get_all_values()
        if not all_data or len(all_data) < 2:
            return render_template('absentees.html', absentees=[], date=datetime.now().strftime('%Y-%m-%d'))

        today = datetime.now().strftime('%Y-%m-%d')
        headers = all_data[0]
        if today not in headers:
            return render_template('absentees.html', absentees=[], date=today)

        records = sheet.get_all_records()
        absentees = [r['Name'] for r in records if r.get(today) == 'Absent']
        return render_template('absentees.html', absentees=absentees, date=today)

    except Exception as e:
        print("Absentees fetch error:", e)
        return render_template('absentees.html', absentees=[], date=datetime.now().strftime('%Y-%m-%d'))

def upload_to_drive(file_path, file_name, folder_id):
    creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/png')
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded.get('id')

@app.route('/add-student', methods=['GET', 'POST'])
def add_student():
    if 'user' not in session:
        return redirect('/')
    if request.method == 'POST':
        name = request.form['name']
        photo_data = request.form['photo']
        if photo_data:
            try:
                header, encoded = photo_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                filename = f"{name}.png"
                os.makedirs("data", exist_ok=True)
                local_path = os.path.join("data", filename)
                with open(local_path, "wb") as f:
                    f.write(image_bytes)
                upload_to_drive(local_path, filename, '1kdtb-fm3ORGf-ZTJ75VPu5uh_e5NYOUm')
            except Exception as e:
                print("Image processing error:", e)
                return "Invalid image data", 400

        try:
            existing_data = sheet.get_all_values()
            new_row = [name] + ['' for _ in range(len(existing_data[0]) - 1)]
            sheet.append_row(new_row)
        except Exception as e:
            print("Google Sheet append error:", e)
            return "Sheet update failed", 500

        return render_template('dashboard.html', msg="Student added and photo uploaded successfully.")
    return render_template('add_student.html')

@app.route('/remove-student', methods=['GET', 'POST'])
def remove_student():
    if 'user' not in session:
        return redirect('/')
    student_names = [row[0] for row in sheet.get_all_values()[1:]]
    if request.method == 'POST':
        name_to_remove = request.form['name']
        records = sheet.get_all_values()
        for idx, row in enumerate(records):
            if row[0] == name_to_remove:
                sheet.delete_rows(idx + 1)
                break
        return render_template('remove_student.html', students=[row[0] for row in sheet.get_all_values()[1:]], msg=f"{name_to_remove} removed.")
    return render_template('remove_student.html', students=student_names)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000) 
