from flask import Flask, render_template, request, redirect, session, jsonify
import os, json, base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from werkzeug.utils import secure_filename
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import numpy as np
import cv2
from openpyxl import load_workbook, Workbook

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
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

# === Recognizer Setup ===
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

# === Attendance Helpers ===
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

@app.route('/', methods=['GET', 'POST'])
def index():
    result_img = None
    message = None

    if request.method == 'POST':
        file = request.files['image']
        if not file:
            return 'No file uploaded', 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        img = cv2.imread(filepath)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        recognized_names = set()
        for (x, y, w, h) in faces:
            roi = gray[y:y + h, x:x + w]
            try:
                label_id_pred, confidence = recognizer.predict(roi)
                if confidence < 70:
                    name = label_map[label_id_pred]
                    recognized_names.add(name)
                    cv2.putText(img, name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                else:
                    name = "Unknown"
            except:
                name = "Unknown"
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)

        result_path = os.path.join(app.config['UPLOAD_FOLDER'], f"result_{filename}")
        cv2.imwrite(result_path, img)

        if recognized_names:
            date_header = datetime.now().strftime("%Y-%m-%d")
            for name in recognized_names:
                update_google_sheet(sheet, date_header, name)
                update_excel(date_header, name)
            message = f"✅ Attendance taken for: {', '.join(recognized_names)}"
        else:
            message = "❌ No known faces recognized!"

        return render_template('index.html', result_img=result_path, message=message)

    return render_template('index.html', result_img=result_img, message=message)

def upload_to_drive(file_path, file_name, folder_id):
    drive_service = build('drive', 'v3', credentials=credentials)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/png')
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded.get('id')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
