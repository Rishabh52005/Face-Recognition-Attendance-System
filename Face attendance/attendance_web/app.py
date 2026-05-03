
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import mysql.connector
import pickle
import numpy as np
import face_recognition
import cv2
import base64
import os
from datetime import date, datetime, timedelta
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'face_attendance_secret_key_change_in_prod'
JWT_SECRET_KEY = app.secret_key  # Use same secret for JWT
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file

# Ensure upload dir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# DB config (matching existing)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Chugh123@',
    'database': 'face_attendance'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def create_users_table():
    """Create users table if not exists"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def format_user_display_name(email):
    local_part = (email or 'user').split('@')[0]
    normalized = local_part.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    display_name = ' '.join(part.capitalize() for part in normalized.split())
    return display_name or 'User'


def create_access_token(user_id, role, email, remember=False):
    expiry = timedelta(days=30) if remember else timedelta(days=7)
    payload = {
        'user_id': user_id,
        'role': role,
        'email': email,
        'exp': datetime.utcnow() + expiry
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

def get_user_role(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user['role'] if user else 'user'

def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def set_auth_cookie(response, token, remember=False):
    cookie_options = {
        'httponly': True,
        'samesite': 'Lax',
        'secure': request.is_secure
    }
    if remember:
        response.set_cookie('access_token', token, max_age=30 * 24 * 60 * 60, **cookie_options)
    else:
        response.set_cookie('access_token', token, **cookie_options)


def clear_auth_cookie(response):
    response.set_cookie(
        'access_token',
        '',
        expires=0,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure
    )


def get_current_user():
    token = request.cookies.get('access_token')
    if not token:
        return None

    token_payload = verify_token(token)
    if not token_payload or not token_payload.get('user_id'):
        return None

    email = token_payload.get('email') or ''
    return {
        'id': token_payload['user_id'],
        'role': token_payload.get('role', 'user'),
        'email': email,
        'display_name': format_user_display_name(email),
        'avatar_name': format_user_display_name(email)
    }


@app.context_processor
def inject_current_user():
    return {'current_user': get_current_user()}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('access_token')
        if not token:
            flash('Please log in to access this page')
            return redirect(url_for('login'))
        token_payload = verify_token(token)
        if not token_payload or not token_payload.get('user_id'):
            flash('Session expired. Please log in again.')
            resp = make_response(redirect(url_for('login')))
            clear_auth_cookie(resp)
            return resp
        return f(user_id=token_payload['user_id'], *args, **kwargs)
    return decorated_function

# Comment out unused RBAC routes
# @app.route('/admin-dashboard')
# @login_required
# def admin_dashboard(user_id):
#     ... 

# @app.route('/user-dashboard')
# @login_required
# def user_dashboard(user_id):
#     ...

# @app.route('/all-attendance')
# @admin_required
# def all_attendance(user_id):
#     ...


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('access_token')
        if not token:
            flash('Please log in to access this page')
            return redirect(url_for('login'))
        token_payload = verify_token(token)
        if not token_payload or not token_payload.get('user_id'):
            flash('Session expired. Please log in again.')
            resp = make_response(redirect(url_for('login')))
            clear_auth_cookie(resp)
            return resp
        user_id = token_payload['user_id']
        role = get_user_role(user_id)
        if role != 'admin':
            flash('Admin access required')
            return redirect(url_for('index'))
        return f(user_id=user_id, role=role, *args, **kwargs)
    return decorated_function

# Init DB
create_users_table()

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('signup.html')
        
        password_hash = generate_password_hash(password)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, password_hash))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Account created successfully! Please log in.')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Email already exists. Please use a different email or log in.')
        except Exception as e:
            flash(f'Error creating account: {str(e)}')
        return render_template('signup.html')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = request.form.get('remember') == 'on'
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            role = get_user_role(user['id'])
            token = create_access_token(user['id'], role, user['email'], remember=remember)
            resp = make_response(redirect(url_for('index')))
            set_auth_cookie(resp, token, remember=remember)
            flash(f'Login successful! Welcome, {role}.')
            return resp
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(user_id):
    resp = make_response(redirect(url_for('login')))
    clear_auth_cookie(resp)
    flash('Logged out successfully!')
    return resp

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard(user_id, role):
    # Keep the legacy admin dashboard URL working, but use the shared dashboard page.
    return redirect(url_for('index'))

@app.route('/user-dashboard')
@login_required
def user_dashboard(user_id):
    return redirect(url_for('index'))

@app.route('/all-attendance')
@admin_required
def all_attendance(user_id, role):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, s.name, s.roll_no 
        FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        ORDER BY a.date DESC, a.time DESC
    """)
    all_attendance = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('all_attendance.html', all_attendance=all_attendance, is_admin=True)

@app.route('/')
@login_required
def index(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    today = date.today().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT a.*, s.name, s.roll_no 
        FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        WHERE a.date = %s 
        ORDER BY a.time
    """, (today,))
    attendance = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as present FROM attendance WHERE date = %s", (today,))
    present_count = cursor.fetchone()['present']
    
    cursor.execute("SELECT COUNT(*) as total FROM students")
    total_students = cursor.fetchone()['total']
    
    percentage = round((present_count / total_students * 100), 1) if total_students > 0 else 0.0
    
    cursor.close()
    conn.close()
    return render_template('index.html', attendance=attendance, today=today, percentage=percentage, present_count=present_count, total_students=total_students)

@app.route('/history')
@admin_required
def history(user_id, role):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, s.name, s.roll_no 
        FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        ORDER BY a.date DESC, a.time DESC
    """)
    history = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('history.html', history=history, is_admin=(role == 'admin'))

@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register(user_id, role):
    if request.method == 'POST':
        name = request.form['name']
        roll_no = request.form['roll_no']
        if 'image' not in request.files:
            flash('No image file selected')
            return redirect(request.url)
        file = request.files['image']
        if file.filename == '':
            flash('No image selected')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Load and encode face
            image = face_recognition.load_image_file(filepath)
            encodings = face_recognition.face_encodings(image)
            if not encodings:
                flash('No face detected in image')
                os.remove(filepath)
                return redirect(request.url)
            encoding = pickle.dumps(encodings[0])
            
            # Save to DB
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO students (name, roll_no) VALUES (%s, %s)", (name, roll_no))
            student_id = cursor.lastrowid
            cursor.execute("INSERT INTO face_embeddings (student_id, embedding) VALUES (%s, %s)", (student_id, encoding))
            conn.commit()
            cursor.close()
            conn.close()
            os.remove(filepath)  # Clean up
            flash('Student registered successfully!')
            return redirect(url_for('index'))
    return render_template('register.html', is_admin=True)

@app.route('/students')
@admin_required
def students(user_id, role):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students ORDER BY name")
    students_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('students.html', students=students_list, is_admin=True, role=role)

@app.route('/mark_attendance')
@admin_required
def mark_attendance(user_id, role):
    return render_template('mark_attendance.html')

@app.route('/stats')
@admin_required
def stats(user_id, role):
    return render_template('stats.html')

@app.route('/api/stats')
@login_required
def api_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Total students
    cursor.execute("SELECT COUNT(*) as total FROM students")
    total_students = cursor.fetchone()['total'] or 0
    
    # Today's attendance
    today = date.today().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT COUNT(DISTINCT student_id) as present_today
        FROM attendance
        WHERE date = %s AND status = 'Present'
    """, (today,))
    present_today = cursor.fetchone()['present_today'] or 0
    absent_today = max(total_students - present_today, 0)

    cursor.execute("""
        SELECT
            COUNT(DISTINCT date) as total_attendance_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as total_present_records,
            MAX(date) as latest_attendance_date
        FROM attendance
    """)
    attendance_overview = cursor.fetchone() or {}
    total_attendance_days = attendance_overview.get('total_attendance_days') or 0
    total_present_records = int(attendance_overview.get('total_present_records') or 0)
    latest_attendance_date = attendance_overview.get('latest_attendance_date')

    today_rate = round((present_today / total_students) * 100, 1) if total_students else 0.0
    overall_rate = round((total_present_records / (total_attendance_days * total_students)) * 100, 1) if total_students and total_attendance_days else 0.0
    average_daily_present = round((total_present_records / total_attendance_days), 1) if total_attendance_days else 0.0

    cursor.execute("""
        SELECT
            date,
            COUNT(DISTINCT CASE WHEN status = 'Present' THEN student_id END) as present_count
        FROM attendance
        GROUP BY date
        ORDER BY date
    """)
    trend_rows = cursor.fetchall()
    trend = []
    for row in trend_rows:
        present_count = row['present_count'] or 0
        trend.append({
            'date': row['date'].isoformat() if row.get('date') else None,
            'present_count': present_count,
            'attendance_rate': round((present_count / total_students) * 100, 1) if total_students else 0.0
        })
    
    cursor.execute("""
        SELECT
            s.student_id,
            s.name,
            s.roll_no,
            COUNT(DISTINCT CASE WHEN a.status = 'Present' THEN a.date END) as present_days,
            MAX(CASE WHEN a.status = 'Present' THEN a.date END) as last_present_date
        FROM students s
        LEFT JOIN attendance a ON a.student_id = s.student_id
        GROUP BY s.student_id, s.name, s.roll_no
        ORDER BY s.name
    """)
    raw_student_stats = cursor.fetchall()

    students_list = []
    student_summaries = []
    for student in raw_student_stats:
        present_days = student['present_days'] or 0
        absent_days = max(total_attendance_days - present_days, 0)
        attendance_rate = round((present_days / total_attendance_days) * 100, 1) if total_attendance_days else 0.0
        last_present_date = student['last_present_date']

        students_list.append({
            'student_id': student['student_id'],
            'name': student['name'],
            'roll_no': student['roll_no']
        })
        student_summaries.append({
            'student_id': student['student_id'],
            'name': student['name'],
            'roll_no': student['roll_no'],
            'total_days': total_attendance_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'attendance_rate': attendance_rate,
            'last_present_date': last_present_date.isoformat() if last_present_date else None
        })
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'total_students': total_students,
        'present_today': present_today,
        'absent_today': absent_today,
        'today_rate': today_rate,
        'overall_rate': overall_rate,
        'total_attendance_days': total_attendance_days,
        'total_present_records': total_present_records,
        'average_daily_present': average_daily_present,
        'latest_attendance_date': latest_attendance_date.isoformat() if latest_attendance_date else None,
        'trend': trend,
        'students_list': students_list,
        'student_summaries': student_summaries
    })

@app.route('/api/student-stats')
@login_required
def api_student_stats(user_id):
    student_id = request.args.get('student_id', type=int)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if student_id:
        cursor.execute("SELECT name, roll_no FROM students WHERE student_id = %s", (student_id,))
        student = cursor.fetchone()
        if not student:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Student not found'}), 404

        cursor.execute("""
            SELECT 
                YEAR(date) as year,
                MONTH(date) as month,
                COUNT(DISTINCT date) as active_days
            FROM attendance
            GROUP BY YEAR(date), MONTH(date)
            ORDER BY YEAR(date), MONTH(date)
        """)
        active_months = cursor.fetchall()

        cursor.execute("""
            SELECT
                YEAR(date) as year,
                MONTH(date) as month,
                COUNT(DISTINCT date) as present_days
            FROM attendance
            WHERE student_id = %s AND status = 'Present'
            GROUP BY YEAR(date), MONTH(date) 
            ORDER BY YEAR(date), MONTH(date)
        """, (student_id,))
        present_months = {
            (row['year'], row['month']): row['present_days'] or 0
            for row in cursor.fetchall()
        }
        
        cursor.close()
        conn.close()
        
        monthly_data = []
        total_present_days = 0
        total_active_days = 0
        for row in active_months:
            key = (row['year'], row['month'])
            active_days = row['active_days'] or 0
            present_days = present_months.get(key, 0)
            total_active_days += active_days
            total_present_days += present_days
            monthly_data.append({
                'label': datetime(row['year'], row['month'], 1).strftime('%b %Y'),
                'year': row['year'],
                'month': row['month'],
                'active_days': active_days,
                'present_days': present_days,
                'absent_days': max(active_days - present_days, 0),
                'attendance_rate': round((present_days / active_days) * 100, 1) if active_days else 0.0
            })
        
        return jsonify({
            'student_name': student['name'],
            'student_roll_no': student['roll_no'],
            'monthly_data': monthly_data,
            'overall_percentage': round((total_present_days / total_active_days) * 100, 1) if total_active_days else 0.0
        })
    else:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Student ID required'}), 400

@app.route('/api/attendance-percentage')
@login_required
def api_attendance_percentage(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    today = date.today().strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT COUNT(*) as present FROM attendance a 
        JOIN students s ON a.student_id = s.student_id 
        WHERE a.date = %s
    """, (today,))
    present = cursor.fetchone()['present']
    
    cursor.execute("SELECT COUNT(*) as total FROM students")
    total = cursor.fetchone()['total']
    
    cursor.close()
    conn.close()
    
    percentage = round((present / total * 100), 1) if total > 0 else 0.0
    
    return jsonify({'percentage': percentage, 'present': present, 'total': total, 'today': today})

@app.route('/recognize', methods=['POST'])
def recognize():
    try:
        data = request.get_json()
        image_data = data['image'].split(',')[1]  # Remove data URL prefix
        nparr = np.frombuffer(base64.b64decode(image_data), np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb)
        face_encodings = face_recognition.face_encodings(rgb, face_locations)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, embedding FROM face_embeddings")
        db_data = cursor.fetchall()
        
        known_encodings = [pickle.loads(row[1]) for row in db_data]
        student_ids = [row[0] for row in db_data]
        
        cursor.close()
        conn.close()
        
        for encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, encoding)
            face_distances = face_recognition.face_distance(known_encodings, encoding)
            
            best_match = np.argmin(face_distances)
            if matches[best_match] and face_distances[best_match] < 0.6:
                student_id = student_ids[best_match]
                
                conn2 = get_db_connection()
                cursor2 = conn2.cursor()
                cursor2.execute("SELECT name FROM students WHERE student_id=%s", (student_id,))
                name_row = cursor2.fetchone()
                name = name_row[0] if name_row else "Unknown"
                cursor2.close()
                conn2.close()
                
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                
                conn3 = get_db_connection()
                cursor3 = conn3.cursor()
                cursor3.execute("SELECT COUNT(*) FROM attendance WHERE student_id=%s AND date=%s", (student_id, today))
                count = cursor3.fetchone()[0]
                
                if count == 0:
                    cursor3.execute(
                        "INSERT INTO attendance(student_id, date, time, status) VALUES(%s, %s, %s, %s)",
                        (student_id, today, now.strftime("%H:%M:%S"), "Present")
                    )
                    conn3.commit()
                    cursor3.close()
                    conn3.close()
                    return jsonify({'success': True, 'student_name': name, 'message': 'Attendance marked successfully!'})
                else:
                    cursor3.close()
                    conn3.close()
                    return jsonify({'success': True, 'student_name': name, 'message': 'Already marked today'})
        
        return jsonify({'success': False, 'message': 'No match found. Try again.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)
