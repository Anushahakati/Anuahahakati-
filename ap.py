from flask import Flask, request, redirect, url_for, render_template_string
import csv
import os
from datetime import date

app = Flask(__name__)

# HTML template as string
attendance_form_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Take Attendance</title>
</head>
<body>
    <h2>Take Attendance</h2>
    <form method="POST">
        <label>Student Name:</label><br>
        <input type="text" name="student_name" required><br><br>
        
        <label>Status:</label><br>
        <select name="status">
            <option value="Present">Present</option>
            <option value="Absent">Absent</option>
        </select><br><br>

        <input type="submit" value="Submit Attendance">
    </form>
    <br>
    <a href="{{ url_for('view_attendance') }}">View Attendance Records</a>
</body>
</html>
'''

# View attendance records
view_attendance_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Attendance Records</title>
</head>
<body>
    <h2>Attendance Records</h2>
    <table border="1">
        <tr>
            <th>Date</th>
            <th>Student Name</th>
            <th>Status</th>
        </tr>
        {% for row in records %}
        <tr>
            <td>{{ row[0] }}</td>
            <td>{{ row[1] }}</td>
            <td>{{ row[2] }}</td>
        </tr>
        {% endfor %}
    </table>
    <br>
    <a href="{{ url_for('take_attendance') }}">Back to Attendance Form</a>
</body>
</html>
'''

@app.route('/take-attendance', methods=['GET', 'POST'])
def take_attendance():
    if request.method == 'POST':
        student_name = request.form['student_name']
        status = request.form['status']
        today = date.today().isoformat()

        # Ensure data directory and file exist
        os.makedirs('data', exist_ok=True)
        file_path = 'data/attendance.csv'

        # Write header if file is new
        write_header = not os.path.exists(file_path)
        with open(file_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(['Date', 'Student Name', 'Status'])
            writer.writerow([today, student_name, status])

        return redirect(url_for('view_attendance'))

    return render_template_string(attendance_form_html)

@app.route('/view-attendance')
def view_attendance():
    file_path = 'data/attendance.csv'
    records = []

    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            records = list(reader)

    return render_template_string(view_attendance_html, records=records)

if __name__ == '__main__':
    app.run(debug=True)
