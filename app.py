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
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_b64 = os.environ.get('GOOGLE_CREDS_B64')
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
    return render_template('dashboard.html')

@app.route('/run_attendance')
def run_attendance():
    if 'user' not in session:
        return redirect('/')

    inp = 'CS101'
    wb_path = 'attend.xlsx'
    rb = load_workbook(wb_path)

    if inp in rb.sheetnames:
        sheetx = rb[inp]
    else:
        sheetx = rb.create_sheet(inp)
        sheetx.cell(row=1, column=1, value='Name-Rollno')

    column_number = sheetx.max_column + 1
    attendance_time = datetime.now().strftime("%Y-%m-%d")
    sheetx.cell(row=1, column=column_number, value=attendance_time)

    already_marked = set()
    TIME_LIMIT_SECONDS = 10
    start_time = time.time()

    cap = cv2.VideoCapture(0)
    detector = cv2.QRCodeDetector()

    os.makedirs("attendance_images", exist_ok=True)

    while time.time() - start_time < TIME_LIMIT_SECONDS:
        ret, frame = cap.read()
        if not ret:
            break

        data, bbox, _ = detector.detectAndDecode(frame)
        if data:
            name = data.strip()
            if name and name not in already_marked:
                found = False
                for cell in sheetx['A']:
                    if cell.value == name:
                        found = True
                        row = cell.row
                        break
                if found:
                    sheetx.cell(row=row, column=column_number, value="Present")
                else:
                    row = sheetx.max_row + 1
                    sheetx.cell(row=row, column=1, value=name)
                    sheetx.cell(row=row, column=column_number, value="Present")

                rb.save(wb_path)
                already_marked.add(name)

                filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                save_path = os.path.join("attendance_images", filename)
                cv2.imwrite(save_path, frame)

                try:
                    upload_to_drive(save_path, filename, '146S39x63_ycnNpv9vgtLOE18cx-54ghG')
                except Exception as e:
                    print("Drive upload failed:", e)

                cv2.putText(frame, f"Scanned: {name}", (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('QR Attendance', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return render_template('dashboard.html', msg="✅ Attendance finished (QR Code Based)")

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
    today = datetime.now().strftime('%Y-%m-%d')
    records = sheet.get_all_records()
    absentees = [r['Name'] for r in records if r.get(today) == 'Absent']
    return render_template('absentees.html', absentees=absentees, date=today)

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

                if os.path.exists("SmartAttendanceWeb"):
                    os.makedirs(os.path.join("SmartAttendanceWeb", "data"), exist_ok=True)
                    git_path = os.path.join("SmartAttendanceWeb", "data", filename)
                    with open(git_path, "wb") as f:
                        f.write(image_bytes)

                upload_to_drive(local_path, filename, '146S39x63_ycnNpv9vgtLOE18cx-54ghG')
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

# ✨ New route added here
@app.route('/take_attendance', methods=['POST'])
def take_attendance():
    if 'user' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    image_data = data.get('image')

    if not image_data:
        return jsonify({'message': 'No image received'}), 400

    try:
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)

        if not data:
            return jsonify({'message': 'No QR code detected'}), 400

        name = data.strip()
        if not name:
            return jsonify({'message': 'Empty QR code data'}), 400

        wb_path = 'attend.xlsx'
        inp = 'CS101'
        rb = load_workbook(wb_path)

        if inp not in rb.sheetnames:
            sheetx = rb.create_sheet(inp)
            sheetx.cell(row=1, column=1, value='Name-Rollno')
        else:
            sheetx = rb[inp]

        column_number = sheetx.max_column + 1
        today = datetime.now().strftime('%Y-%m-%d')
        sheetx.cell(row=1, column=column_number, value=today)

        found = False
        for cell in sheetx['A']:
            if cell.value == name:
                row = cell.row
                found = True
                break

        if not found:
            row = sheetx.max_row + 1
            sheetx.cell(row=row, column=1, value=name)

        sheetx.cell(row=row, column=column_number, value="Present")
        rb.save(wb_path)

        return jsonify({'message': f'✅ {name} marked Present'})

    except Exception as e:
        print("Error processing attendance:", str(e))
        return jsonify({'message': 'Something went wrong processing the image'}), 500

# 🚀 Start app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
