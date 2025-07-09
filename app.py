from flask import Flask, render_template, request, redirect, session
import gspread
import os, json, base64, time
from google.oauth2.service_account import Credentials
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from openpyxl import load_workbook
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

    inp = 'CS101'  # Replace with your logic
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

    TIME_LIMIT_SECONDS = 5
    start_time = time.time()
    already_marked = set()

    # Initialize QR scanner
    capture = cv2.VideoCapture(0)
    detector = cv2.QRCodeDetector()

    while True:
        if time.time() - start_time > TIME_LIMIT_SECONDS:
            break

        ret, frame = capture.read()
        if not ret:
            break

        data, bbox, _ = detector.detectAndDecode(frame)
        if data:
            name = data.strip()
            if name and name not in already_marked:
                # Check if name already exists
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
                already_marked.add(name)
                rb.save(wb_path)

                # Visual feedback
                cv2.putText(frame, f"Scanned: {name}", (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('QR Attendance', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    capture.release()
    cv2.destroyAllWindows()
    return render_template('dashboard.html', msg="✅ Attendance finished (QR Code Based)")

# === Start Server ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
