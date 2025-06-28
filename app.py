
from flask import Flask, render_template, request, redirect, session, url_for
import subprocess
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret_key'  # Replace with a secure key

# Google Sheets setup
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key('1j5cxov8g0jl4Ou6M2ehzcwA-MPBXO8pn85nHTCHFqAg')
sheet = spreadsheet.worksheet("Attendance")

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'bcca' and request.form['password'] == 'bcca':
            session['user'] = 'admin'
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Invalid Credentials')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html')

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
    headers = records[0][1:]  # Exclude 'Name'
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

@app.route('/run_attendance')
def run_attendance():
    if 'user' not in session:
        return redirect('/')
    subprocess.Popen(["python", "chat.py"])
    return render_template('dashboard.html', msg="Attendance script started.")

if __name__ == '__main__':
    app.run(debug=True)
