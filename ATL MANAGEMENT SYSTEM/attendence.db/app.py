from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
# Production
import os
from datetime import datetime
import os
import pdfkit
import tempfile
import sqlite3
from werkzeug.utils import secure_filename
import re
import uuid



app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['DEBUG'] = True
db = DatabaseManager()

DEVELOPER_USERNAME = "DAV_ATL"
DEVELOPER_PASSWORD = "DAV_BAKHRI"
ATTENDANCE_USERNAME = "ATL_21"
ATTENDANCE_PASSWORD = "ATL"
TEACHER_USERNAME = "ATL_TEACHER"
TEACHER_PASSWORD = "ATL_DAV"

UPLOAD_FOLDER = 'static/project_files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

def init_db():
    create_tables()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students')
        if cursor.fetchone()[0] == 0:
            print("New database initialized!")
        else:
            print("Using existing database.")

def allowed_file(filename):
    # Allow all file types
    return True  # This will allow any file type
    
    # Or if you want to allow specific types but more than before:
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
        'jpg', 'jpeg', 'png', 'gif', 'zip', 'rar', '7z',
        'py', 'java', 'cpp', 'c', 'html', 'css', 'js',
        'mp3', 'mp4', 'avi', 'mov',
        'csv', 'json', 'xml'
    }
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if 'user_role' not in session:
        return redirect(url_for('login'))
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                message_id,
                user_name,
                user_role,
                message,
                timestamp
            FROM open_chat
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        chat_messages = cursor.fetchall()
    
    # Redirect students to their dashboard
    if session.get('user_role') == 'student':
        return redirect(url_for('student_dashboard'))
    
    # Both teachers and developers will see the main dashboard
    return render_template('dashboard.html', 
                         chat_messages=chat_messages,
                         current_user_role=session.get('user_role'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == DEVELOPER_USERNAME and password == DEVELOPER_PASSWORD:
            session['user_role'] = 'developer'
            flash('Welcome Core Member Team!')
            return redirect(url_for('index'))
        elif username == TEACHER_USERNAME and password == TEACHER_PASSWORD:
            session['user_role'] = 'teacher'  # Set role as teacher
            flash('Welcome Teacher!')
            return redirect(url_for('index'))  # Redirect to main dashboard instead of teacher_dashboard
        elif username == ATTENDANCE_USERNAME and password == ATTENDANCE_PASSWORD:
            session['user_role'] = 'attendance_marker'
            flash('Welcome Management Team!')
            return redirect(url_for('index'))
        else:
            # Check for student login using admission number
            with sqlite3.connect('attendance.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT student_id, name, password 
                    FROM students 
                    WHERE admission_no = ?
                ''', (username,))
                student = cursor.fetchone()
                
                
                if student and student[2] == password:
                    session['user_role'] = 'student'
                    session['student_id'] = student[0]
                    session['student_name'] = student[1]
                    flash(f'Welcome {student[1]}!')
                    return redirect(url_for('student_dashboard'))
                else:
                    flash('Invalid credentials. Please try again.')
                    
        return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        try:
            admission_no = request.form['admission_no'].strip().upper()
            name = request.form['name'].strip()
            fathers_name = request.form['fathers_name'].strip()
            mothers_name = request.form['mothers_name'].strip()
            class_name = request.form['class'].strip()
            roll_number = request.form['roll']
            section = request.form['section'].strip()
            course = request.form['course'].strip()
            email = request.form['email'].strip()
            dob = request.form['dob'].strip()
            phone = request.form['phone'].strip()
            address = request.form['address'].strip()
            
            if not validate_admission_no(admission_no):
                flash('Invalid admission number format. Use 3 letters followed by 4 or more numbers (e.g., ATL1234)')
                return redirect(url_for('add_student'))
            
            if not all([admission_no, name, fathers_name, mothers_name, 
                       class_name, roll_number, section, course, email,
                       phone, address, dob]):
                flash('All fields are required!')
                return redirect(url_for('add_student'))
            
            # Create password from DOB
            password = dob
            
            if db.add_student(admission_no, name, fathers_name, mothers_name,
                            class_name, roll_number, section, course,
                            email, phone, address, dob, password):
                flash('Student added successfully!')
            else:
                flash('Error adding student. Please check the data and try again.')
            
        except Exception as e:
            flash(f'Error: {str(e)}')
            
        return redirect(url_for('add_student'))
        
    return render_template('add_student.html')

@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    if session.get('user_role') not in ['developer', 'teacher', 'attendance_marker']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        student_id = request.form['student_id']
        status = request.form['status']
        date = datetime.now().strftime('%Y-%m-%d')
        
        success, message = db.mark_attendance(student_id, date, status)
        if success:
            flash('Attendance marked successfully!')
        else:
            flash(f'Error: {message}')
        return redirect(url_for('mark_attendance'))
        
    # Get list of students who haven't had attendance marked today
    today = datetime.now().strftime('%Y-%m-%d')
    students = db.get_students_without_attendance(today)
    return render_template('mark_attendance.html', students=students)

@app.route('/view_students')
def view_students():
    if session.get('user_role') not in ['developer', 'teacher', 'attendance_marker']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    search_query = request.args.get('search', '').strip()
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        if search_query:
            cursor.execute('''
                SELECT s.*, COUNT(p.project_id) as project_count 
                FROM students s 
                LEFT JOIN projects p ON s.student_id = p.student_id
                WHERE s.name LIKE ? OR s.roll_number LIKE ? OR s.class LIKE ?
                GROUP BY s.student_id
            ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute('''
                SELECT s.*, COUNT(p.project_id) as project_count 
                FROM students s 
                LEFT JOIN projects p ON s.student_id = p.student_id
                GROUP BY s.student_id
            ''')
            
        students = cursor.fetchall()
    return render_template('view_students.html', students=students, search_query=search_query)

@app.route('/student_details/<int:student_id>')
def student_details(student_id):
    # Update permissions to include teacher
    if session.get('user_role') == 'student' and session.get('student_id') != student_id:
        flash('Access denied')
        return redirect(url_for('student_dashboard'))
    elif session.get('user_role') not in ['developer', 'teacher', 'attendance_marker']:
        return redirect(url_for('login'))
        
    student = db.get_student_details(student_id)
    attendance = db.get_student_attendance(student_id)
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get issued components for the student
        cursor.execute('''
            SELECT ic.issue_id, c.component_name, ic.quantity, 
                   ic.issue_date, ic.return_date
            FROM issued_components ic
            JOIN components c ON ic.component_id = c.component_id
            WHERE ic.student_id = ?
        ''', (student_id,))
        issued_components = cursor.fetchall()
        
        # Get available components for issuing
        cursor.execute('SELECT * FROM components WHERE available_quantity > 0')
        available_components = cursor.fetchall()
        
    return render_template('student_details.html', 
                         student=student,
                         attendance=attendance,
                         issued_components=issued_components,
                         available_components=available_components)

@app.route('/check_attendance', methods=['GET', 'POST'])
def check_attendance():
    if session.get('user_role') not in ['developer', 'teacher', 'attendance_marker']:
        flash('Access denied')
        return redirect(url_for('index'))
    
    attendance_data = None
    selected_date = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
        
    if request.method == 'POST':
        if 'export_pdf' in request.form:
            # Generate PDF
            attendance_data = db.get_attendance_by_date_range(selected_date, selected_date)
            if attendance_data:
                return generate_attendance_pdf(attendance_data, selected_date)
            else:
                flash('No attendance data found for selected date')
        else:
            # Normal date filter
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            attendance_data = db.get_attendance_by_date_range(start_date, end_date)
    else:
        attendance_data = db.get_attendance_by_date_range()
        
    return render_template('check_attendance.html', 
                         attendance_data=attendance_data, 
                         selected_date=selected_date)

def generate_attendance_pdf(attendance_data, date):
    # Create HTML content for PDF
    html_content = f'''
    <html>
        <head>
            <style>
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid black; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .present {{ color: green; }}
                .absent {{ color: red; }}
                h2 {{ text-align: center; }}
            </style>
        </head>
        <body>
            <h2>Attendance Report - {date}</h2>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Class</th>
                        <th>Roll Number</th>
                        <th>Section</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for record in attendance_data:
        status_class = 'present' if record[5] == 'present' else 'absent'
        html_content += f'''
            <tr>
                <td>{record[0]}</td>
                <td>{record[1]}</td>
                <td>{record[2]}</td>
                <td>{record[3]}</td>
                <td class="{status_class}">{record[5]}</td>
            </tr>
        '''
    
    html_content += '''
                </tbody>
            </table>
        </body>
    </html>
    '''
    
    # Create temporary file
    temp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False)
    temp_html.write(html_content.encode('utf-8'))
    temp_html.close()
    
    # Generate PDF
    pdf_file = f'attendance_report_{date}.pdf'
    
    try:
        # Try different possible paths for wkhtmltopdf
        possible_paths = [
            'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe',  # Windows default
            'C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe',  # Windows x86
            '/usr/local/bin/wkhtmltopdf',  # Mac/Linux
            '/usr/bin/wkhtmltopdf',  # Linux
            'wkhtmltopdf'  # If in system PATH
        ]
        
        config = None
        for path in possible_paths:
            try:
                config = pdfkit.configuration(wkhtmltopdf=path)
                # Try to generate a small test PDF to verify the path works
                pdfkit.from_string('test', 'test.pdf', configuration=config)
                os.remove('test.pdf')  # Clean up test file
                break
            except Exception:
                continue
        
        if config is None:
            # If no working path found, try without specific path
            pdfkit.from_file(temp_html.name, pdf_file)
        else:
            pdfkit.from_file(temp_html.name, pdf_file, configuration=config)
            
        # Clean up temporary file
        os.unlink(temp_html.name)
        
        # Send PDF file
        return send_file(pdf_file,
                        mimetype='application/pdf',
                        as_attachment=True,
                        download_name=f'attendance_report_{date}.pdf')
                        
    except Exception as e:
        os.unlink(temp_html.name)  # Clean up temp file
        flash(f'Error generating PDF: {str(e)}. Please make sure wkhtmltopdf is installed.')
        return redirect(url_for('check_attendance'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!')
    return redirect(url_for('login'))

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    success, message = db.delete_student(student_id)
    if success:
        flash('Student deleted successfully')
    else:
        flash(f'Error deleting student: {message}')
    
    return redirect(url_for('view_students'))

@app.route('/components')
def components():
    if session.get('user_role') not in ['developer', 'teacher', 'student']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get total counts
        cursor.execute('''
            SELECT 
                COUNT(*) as total_components,
                SUM(total_quantity) as total_items,
                SUM(total_quantity - available_quantity) as issued_items,
                SUM(available_quantity) as available_items
            FROM components
        ''')
        stats = cursor.fetchone()
        
        if session.get('user_role') == 'student':
            # For students, show only their issued components
            student_id = session.get('student_id')
            cursor.execute('''
                SELECT 
                    c.component_name,
                    ic.quantity,
                    ic.issue_date,
                    ic.return_date,
                    ic.issue_id
                FROM issued_components ic
                JOIN components c ON ic.component_id = c.component_id
                WHERE ic.student_id = ?
                ORDER BY ic.issue_date DESC
            ''', (student_id,))
            issued_components = cursor.fetchall()
            return render_template('student_components.html', 
                                issued_components=issued_components,
                                stats=stats)
        else:
            # For developers and attendance markers, show all components
            search_query = request.args.get('search', '').strip()
            
            # Get components with search
            if search_query:
                cursor.execute('''
                    SELECT * FROM components 
                    WHERE component_name LIKE ?
                    ORDER BY component_name
                ''', (f'%{search_query}%',))
            else:
                cursor.execute('SELECT * FROM components ORDER BY component_name')
                
            components = cursor.fetchall()
            
            return render_template('components.html', 
                               components=components,
                               stats=stats,
                               search_query=search_query,
                               is_developer=session.get('user_role') == 'developer')

@app.route('/add_component', methods=['POST'])
def add_component():
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('components'))
        
    try:
        component_name = request.form['component_name'].strip()
        total_quantity = int(request.form['total_quantity'])
        app.logger.debug(f'Received component data - Name: {component_name}, Quantity: {total_quantity}')
        
        if not component_name or total_quantity <= 0:
            flash('Invalid component name or quantity')
            app.logger.warning(f'Invalid input - Name: {component_name}, Quantity: {total_quantity}')
            return redirect(url_for('components'))
            
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            app.logger.debug('Connected to database successfully')
            
            # Verify components table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='components'")
            if not cursor.fetchone():
                app.logger.error('Components table does not exist in database')
                flash('Database error: Components table missing')
                return redirect(url_for('components'))
            
            # Check if component already exists
            cursor.execute('SELECT 1 FROM components WHERE component_name = ?', (component_name,))
            if cursor.fetchone():
                flash('Component already exists')
                app.logger.warning(f'Component already exists: {component_name}')
                return redirect(url_for('components'))
                
            app.logger.debug('Attempting to insert new component')
            cursor.execute('''
                INSERT INTO components (component_name, total_quantity, available_quantity)
                VALUES (?, ?, ?)
            ''', (component_name, total_quantity, total_quantity))
            conn.commit()
            app.logger.debug('Component inserted successfully')
        
        flash('Component added successfully')
        app.logger.info(f"Component added: {component_name}, Quantity: {total_quantity}")
    except ValueError:
        flash('Invalid quantity value')
        app.logger.error(f"Invalid quantity value: {request.form['total_quantity']}")
    except sqlite3.Error as e:
        flash(f'Database error: {str(e)}')
        app.logger.error(f'Database error adding component: {str(e)}')
        if 'no such table' in str(e):
            app.logger.error('Components table does not exist in database')
    except Exception as e:
        flash(f'Error adding component: {str(e)}')
        app.logger.error(f'Error adding component: {str(e)}')
    
    return redirect(url_for('components'))

@app.route('/issue_component', methods=['POST'])
def issue_component():
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('components'))
    
    student_id = request.form['student_id']
    component_id = request.form['component_id']
    quantity = request.form['quantity']
    issue_date = datetime.now().strftime('%Y-%m-%d')
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Check if enough quantity is available
        cursor.execute('SELECT available_quantity FROM components WHERE component_id = ?', (component_id,))
        available = cursor.fetchone()[0]
        
        if available >= int(quantity):
            # Issue component
            cursor.execute('''
                INSERT INTO issued_components 
                (student_id, component_id, quantity, issue_date)
                VALUES (?, ?, ?, ?)
            ''', (student_id, component_id, quantity, issue_date))
            
            # Update available quantity
            cursor.execute('''
                UPDATE components 
                SET available_quantity = available_quantity - ?
                WHERE component_id = ?
            ''', (quantity, component_id))
            
            conn.commit()
            flash('Component issued successfully')
        else:
            flash('Not enough quantity available')
    
    return redirect(url_for('student_details', student_id=student_id))

@app.route('/return_component/<int:issue_id>', methods=['POST'])
def return_component(issue_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('components'))
    
    return_date = datetime.now().strftime('%Y-%m-%d')
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get issue details
        cursor.execute('''
            SELECT component_id, quantity 
            FROM issued_components 
            WHERE issue_id = ?
        ''', (issue_id,))
        component_id, quantity = cursor.fetchone()
        
        # Update return date
        cursor.execute('''
            UPDATE issued_components 
            SET return_date = ? 
            WHERE issue_id = ?
        ''', (return_date, issue_id))
        
        # Update available quantity
        cursor.execute('''
            UPDATE components 
            SET available_quantity = available_quantity + ?
            WHERE component_id = ?
        ''', (quantity, component_id))
        
        conn.commit()
        
        # Get student_id for redirect
        cursor.execute('SELECT student_id FROM issued_components WHERE issue_id = ?', (issue_id,))
        student_id = cursor.fetchone()[0]
    
    return redirect(url_for('student_details', student_id=student_id))

@app.route('/remove_component/<int:component_id>', methods=['POST'])
def remove_component(component_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied. Only administrators can remove components.')
        return redirect(url_for('components'))
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Check if component has any active issues
        cursor.execute('''
            SELECT COUNT(*) 
            FROM issued_components 
            WHERE component_id = ? AND return_date IS NULL
        ''', (component_id,))
        active_issues = cursor.fetchone()[0]
        
        if active_issues > 0:
            flash('Cannot remove component that has active issues')
            return redirect(url_for('components'))
        
        try:
            # Remove all returned issue records
            cursor.execute('''
                DELETE FROM issued_components 
                WHERE component_id = ? AND return_date IS NOT NULL
            ''', (component_id,))
            
            # Remove the component
            cursor.execute('DELETE FROM components WHERE component_id = ?', (component_id,))
            conn.commit()
            flash('Component removed successfully')
        except Exception as e:
            flash(f'Error removing component: {str(e)}')
    
    return redirect(url_for('components'))

@app.route('/student_projects/<int:student_id>')
def student_projects(student_id):
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get student details with all fields
        cursor.execute('''
            SELECT student_id, admission_no, name, fathers_name, mothers_name,
                   class, roll_number, section, course, email, phone, address, dob
            FROM students 
            WHERE student_id = ?
        ''', (student_id,))
        student = cursor.fetchone()
        
        # Get student's projects
        cursor.execute('''
            SELECT p.*, COUNT(pf.file_id) as file_count 
            FROM projects p 
            LEFT JOIN project_files pf ON p.project_id = pf.project_id
            WHERE p.student_id = ?
            GROUP BY p.project_id
        ''', (student_id,))
        projects = cursor.fetchall()
        
    return render_template('student_projects.html', student=student, projects=projects)

@app.route('/add_project/<int:student_id>', methods=['POST'])
def add_project(student_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('student_projects', student_id=student_id))
        
    project_name = request.form['project_name']
    description = request.form['description']
    start_date = datetime.now().strftime('%Y-%m-%d')
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (student_id, project_name, description, start_date)
            VALUES (?, ?, ?, ?)
        ''', (student_id, project_name, description, start_date))
        conn.commit()
        
    flash('Project added successfully')
    return redirect(url_for('student_projects', student_id=student_id))

@app.route('/project_details/<int:project_id>')
def project_details(project_id):
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    # Allow full access to developers and teachers
    if session.get('user_role') not in ['developer', 'teacher', 'student']:
        flash('Access denied')
        return redirect(url_for('index'))

    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get project details
        cursor.execute('''
            SELECT 
                p.project_id,
                p.student_id,
                p.project_name,
                p.description,
                p.start_date,
                p.status,
                s.name as student_name 
            FROM projects p 
            LEFT JOIN students s ON p.student_id = s.student_id 
            WHERE p.project_id = ?
        ''', (project_id,))
        
        # Convert tuple to dictionary
        columns = ['project_id', 'student_id', 'project_name', 'description', 
                  'start_date', 'status', 'student_name']
        row = cursor.fetchone()
        project = dict(zip(columns, row)) if row else None
        
        # Get project files
        cursor.execute('''
            SELECT 
                file_id,
                project_id,
                file_name,
                file_path,
                upload_date,
                description
            FROM project_files 
            WHERE project_id = ?
        ''', (project_id,))
        file_columns = ['file_id', 'project_id', 'file_name', 'file_path', 
                       'upload_date', 'description']
        files = [dict(zip(file_columns, row)) for row in cursor.fetchall()]
        
        # Check if current user is member of this project (for students only)
        is_member = False
        if session.get('user_role') == 'student':
            cursor.execute('''
                SELECT 1 FROM project_members 
                WHERE project_id = ? AND student_id = ?
                UNION
                SELECT 1 FROM projects 
                WHERE project_id = ? AND student_id = ?
            ''', (project_id, session['student_id'], project_id, session['student_id']))
            is_member = cursor.fetchone() is not None
            
        # Get project members for group projects
        cursor.execute('''
            SELECT s.name, s.admission_no, pm.join_date
            FROM project_members pm
            JOIN students s ON pm.student_id = s.student_id
            WHERE pm.project_id = ?
        ''', (project_id,))
        members = cursor.fetchall()
        
    return render_template('project_details.html', 
                         project=project, 
                         files=files,
                         members=members,
                         is_member=is_member or session.get('user_role') in ['developer', 'teacher'],
                         user_role=session.get('user_role'))

@app.route('/upload_project_file/<int:project_id>', methods=['GET', 'POST'])
def upload_project_file(project_id):
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
            
        file = request.files['file']
        
        # Check if a file was selected
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
            
        # Validate file type
        if not allowed_file(file.filename):
            flash('File type not allowed')
            return redirect(request.url)
            
        # Save the file
        try:
            filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())[:8]
            filename = f'{project_id}_{unique_id}_{filename}'
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            file.save(file_path)
            
            # Save file information to database
            with sqlite3.connect('attendance.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO project_files 
                    (project_id, file_name, file_path, upload_date, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (project_id, filename, file_path, 
                     datetime.now().strftime('%Y-%m-%d'),
                     request.form.get('description', '')))
                conn.commit()
                
            flash('File uploaded successfully')
            return redirect(url_for('project_details', project_id=project_id))
            
        except Exception as e:
            flash(f'Error uploading file: {str(e)}')
            return redirect(request.url)
    
    return render_template('upload.html', project_id=project_id)

@app.route('/student_dashboard')
def student_dashboard():
    if session.get('user_role') != 'student':
        return redirect(url_for('login'))
        
    student_id = session['student_id']
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get student details
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()
        
        # Get attendance
        cursor.execute('''
            SELECT date, status 
            FROM attendance 
            WHERE student_id = ? 
            ORDER BY date DESC
        ''', (student_id,))
        attendance = cursor.fetchall()
        
        # Get broadcasts
        cursor.execute('''
            SELECT message, created_at, created_by, broadcast_id 
            FROM broadcasts 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        broadcasts = cursor.fetchall()
        
        # Get individual projects
        cursor.execute('''
            SELECT p.*, COUNT(pf.file_id) as file_count 
            FROM projects p 
            LEFT JOIN project_files pf ON p.project_id = pf.project_id
            WHERE p.student_id = ?
            GROUP BY p.project_id
        ''', (student_id,))
        individual_projects = cursor.fetchall()
        
        # Get group projects
        cursor.execute('''
            SELECT p.*, COUNT(pf.file_id) as file_count 
            FROM projects p 
            JOIN project_members pm ON p.project_id = pm.project_id
            LEFT JOIN project_files pf ON p.project_id = pf.project_id
            WHERE pm.student_id = ? AND p.student_id IS NULL
            GROUP BY p.project_id
        ''', (student_id,))
        group_projects = cursor.fetchall()
        
        # Get chat messages
        cursor.execute('''
            SELECT 
                message_id,
                user_name,
                user_role,
                message,
                timestamp
            FROM open_chat
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        chat_messages = cursor.fetchall()
        
    return render_template('student_dashboard.html', 
                         student=student,
                         attendance=attendance,
                         individual_projects=individual_projects,
                         group_projects=group_projects,
                         broadcasts=broadcasts,
                         chat_messages=chat_messages,
                         current_user_role=session.get('user_role'))

@app.route('/create_group_project', methods=['POST'])
def create_group_project():
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    project_name = request.form['project_name']
    description = request.form['description']
    student_ids = request.form.getlist('student_ids')  # List of selected students
    
    if len(student_ids) < 2:
        flash('Please select at least 2 students for a group project')
        return redirect(url_for('view_students'))
        
    start_date = datetime.now().strftime('%Y-%m-%d')
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        try:
            # Create project
            cursor.execute('''
                INSERT INTO projects (project_name, description, start_date)
                VALUES (?, ?, ?)
            ''', (project_name, description, start_date))
            
            project_id = cursor.lastrowid
            
            # Add project members
            for student_id in student_ids:
                cursor.execute('''
                    INSERT INTO project_members (project_id, student_id, join_date)
                    VALUES (?, ?, ?)
                ''', (project_id, student_id, start_date))
                
            conn.commit()
            flash('Group project created successfully!')
            
        except Exception as e:
            flash(f'Error creating group project: {str(e)}')
            
    return redirect(url_for('view_students'))

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        try:
            admission_no = request.form['admission_no'].strip().upper()
            name = request.form['name'].strip()
            fathers_name = request.form['fathers_name'].strip()
            mothers_name = request.form['mothers_name'].strip()
            class_name = request.form['class'].strip()
            roll_number = request.form['roll']
            section = request.form['section'].strip()
            course = request.form['course'].strip()
            email = request.form['email'].strip()
            phone = request.form['phone'].strip()
            address = request.form['address'].strip()
            dob = request.form['dob'].strip()
            
            if not validate_admission_no(admission_no):
                flash('Invalid admission number format. Use 3 letters followed by 4 or more numbers (e.g., ATL1234)')
                return redirect(url_for('edit_student', student_id=student_id))
            
            if not all([admission_no, name, fathers_name, mothers_name, 
                       class_name, roll_number, section, course, email,
                       phone, address, dob]):
                flash('All fields are required!')
                return redirect(url_for('edit_student', student_id=student_id))
            
            with sqlite3.connect('attendance.db') as conn:
                cursor = conn.cursor()
                
                # Check if admission number exists for other students
                cursor.execute('''
                    SELECT COUNT(*) FROM students 
                    WHERE admission_no = ? AND student_id != ?
                ''', (admission_no, student_id))
                
                if cursor.fetchone()[0] > 0:
                    flash('Admission number already exists!')
                    return redirect(url_for('edit_student', student_id=student_id))
                
                # Update password if DOB changed
                cursor.execute('SELECT dob FROM students WHERE student_id = ?', (student_id,))
                old_dob = cursor.fetchone()[0]
                password = dob if dob != old_dob else old_dob
                
                cursor.execute('''
                    UPDATE students SET 
                        admission_no = ?,
                        name = ?,
                        fathers_name = ?,
                        mothers_name = ?,
                        class = ?,
                        roll_number = ?,
                        section = ?,
                        course = ?,
                        email = ?,
                        phone = ?,
                        address = ?,
                        dob = ?,
                        password = ?
                    WHERE student_id = ?
                ''', (admission_no, name, fathers_name, mothers_name,
                      class_name, roll_number, section, course,
                      email, phone, address, dob, password, student_id))
                
                conn.commit()
                flash('Student details updated successfully!')
                return redirect(url_for('student_details', student_id=student_id))
                
        except Exception as e:
            flash(f'Error updating student: {str(e)}')
            return redirect(url_for('edit_student', student_id=student_id))
    
    # GET request - show edit form
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()
        
        if not student:
            flash('Student not found!')
            return redirect(url_for('view_students'))
            
    return render_template('edit_student.html', student=student)

@app.route('/projects')
def projects():
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    with sqlite3.connect('attendance.db') as conn:
        conn.row_factory = sqlite3.Row  # This will allow dictionary-like access to rows
        cursor = conn.cursor()
        
        if session.get('user_role') == 'student':
            student_id = session.get('student_id')
            
            # Get individual projects with more details
            cursor.execute('''
                SELECT 
                    p.*,
                    COUNT(DISTINCT pf.file_id) as file_count,
                    GROUP_CONCAT(DISTINCT pf.file_name) as file_names
                FROM projects p
                LEFT JOIN project_files pf ON p.project_id = pf.project_id
                WHERE p.student_id = ?
                GROUP BY p.project_id
                ORDER BY p.start_date DESC
            ''', (student_id,))
            individual_projects = cursor.fetchall()
            
            # Get group projects with more details
            cursor.execute('''
                SELECT 
                    p.*,
                    COUNT(DISTINCT pf.file_id) as file_count,
                    GROUP_CONCAT(DISTINCT s.name) as member_names,
                    GROUP_CONCAT(DISTINCT pf.file_name) as file_names
                FROM projects p
                JOIN project_members pm ON p.project_id = pm.project_id
                JOIN students s ON pm.student_id = s.student_id
                LEFT JOIN project_files pf ON p.project_id = pf.project_id
                WHERE pm.student_id = ?
                GROUP BY p.project_id
                ORDER BY p.start_date DESC
            ''', (student_id,))
            group_projects = cursor.fetchall()
            
            return render_template('projects.html',
                                individual_projects=individual_projects,
                                group_projects=group_projects,
                                user_role=session.get('user_role'))
        elif session.get('user_role') in ['developer', 'teacher']:  # Include teacher here
            # For staff and teachers, show all projects with detailed information
            cursor.execute('''
                SELECT 
                    p.project_id as id,
                    p.project_name as name,
                    p.description,
                    p.start_date,
                    p.status,
                    COUNT(DISTINCT pf.file_id) as file_count,
                    CASE 
                        WHEN p.student_id IS NULL THEN 'Group'
                        ELSE 'Individual'
                    END as project_type,
                    COALESCE(
                        (SELECT s.name FROM students s WHERE s.student_id = p.student_id),
                        GROUP_CONCAT(DISTINCT sm.name)
                    ) as member_names,
                    GROUP_CONCAT(DISTINCT pf.file_name) as file_names,
                    p.student_id  -- Add this to get the student ID
                FROM projects p
                LEFT JOIN students s ON p.student_id = s.student_id
                LEFT JOIN project_members pm ON p.project_id = pm.project_id
                LEFT JOIN students sm ON pm.student_id = sm.student_id
                LEFT JOIN project_files pf ON p.project_id = pf.project_id
                GROUP BY p.project_id
                ORDER BY p.start_date DESC
            ''')
            all_projects = cursor.fetchall()
            
            return render_template('projects.html', 
                                all_projects=all_projects,
                                user_role=session.get('user_role'))
        else:
            flash('Access denied')
            return redirect(url_for('index'))

@app.route('/broadcast', methods=['GET', 'POST'])
def broadcast():
    if session.get('user_role') not in ['developer', 'teacher', 'attendance_marker']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if message:
            with sqlite3.connect('attendance.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO broadcasts (message, created_at, created_by)
                    VALUES (?, ?, ?)
                ''', (message, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                      session.get('user_role')))
                conn.commit()
                flash('Broadcast message sent!')
        return redirect(url_for('broadcast'))
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT message, created_at, created_by, broadcast_id 
            FROM broadcasts 
            ORDER BY created_at DESC 
            LIMIT 50
        ''')
        broadcasts = cursor.fetchall()
        
    return render_template('broadcast.html', broadcasts=broadcasts)

@app.route('/delete_broadcast/<int:broadcast_id>', methods=['POST'])
def delete_broadcast(broadcast_id):
    if session.get('user_role') != 'developer':
        flash('Access denied')
        return redirect(url_for('index'))
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM broadcasts WHERE broadcast_id = ?', (broadcast_id,))
        conn.commit()
        flash('Broadcast deleted successfully')
        
    return redirect(url_for('broadcast'))

@app.route('/delete_project/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('projects'))
        
    try:
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            
            # Delete associated files first
            cursor.execute('SELECT file_path FROM project_files WHERE project_id = ?', (project_id,))
            files = cursor.fetchall()
            
            # Delete physical files
            for file in files:
                try:
                    if file[0] and os.path.exists(file[0]):
                        os.remove(file[0])
                except:
                    pass
            
            # Delete from database tables in order
            cursor.execute('DELETE FROM project_files WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM project_chat WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM project_members WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM projects WHERE project_id = ?', (project_id,))
            
            conn.commit()
            flash('Project deleted successfully')
            
    except Exception as e:
        flash(f'Error deleting project: {str(e)}')
        
    return redirect(url_for('projects'))

@app.route('/complete_project/<int:project_id>', methods=['POST'])
def complete_project(project_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('projects'))
        
    try:
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE projects 
                SET status = 'completed', 
                    completion_date = ? 
                WHERE project_id = ?
            ''', (datetime.now().strftime('%Y-%m-%d'), project_id))
            conn.commit()
            flash('Project marked as completed')
            
    except Exception as e:
        flash(f'Error updating project status: {str(e)}')
        
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/download_file/<int:file_id>')
def download_file(file_id):
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT file_path, file_name FROM project_files WHERE file_id = ?', (file_id,))
        result = cursor.fetchone()
        
        if result:
            file_path, file_name = result
            if os.path.exists(file_path):
                return send_file(file_path, 
                               as_attachment=True,
                               download_name=file_name)
                               
    flash('File not found')
    return redirect(request.referrer or url_for('projects'))

@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    try:
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            
            # Get file info before deletion
            cursor.execute('''
                SELECT pf.file_path, pf.project_id 
                FROM project_files pf 
                WHERE pf.file_id = ?
            ''', (file_id,))
            result = cursor.fetchone()
            
            if result:
                file_path, project_id = result
                
                # Delete physical file
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Delete database record
                cursor.execute('DELETE FROM project_files WHERE file_id = ?', (file_id,))
                conn.commit()
                
                flash('File deleted successfully')
                return redirect(url_for('project_details', project_id=project_id))
            
            flash('File not found')
            return redirect(request.referrer or url_for('projects'))
            
    except Exception as e:
        app.logger.error(f"Error deleting file {file_id}: {str(e)}")
        flash('Error deleting file. Please try again.')
        return redirect(request.referrer or url_for('projects'))

def create_tables():
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Add completion_date column to projects table if it doesn't exist
        cursor.execute('''
            SELECT COUNT(*) FROM pragma_table_info('projects') 
            WHERE name='completion_date'
        ''')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                ALTER TABLE projects 
                ADD COLUMN completion_date TEXT
            ''')
            
        # Remove the DROP TABLE commands
        # Create tables only if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admission_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                fathers_name TEXT NOT NULL,
                mothers_name TEXT NOT NULL,
                class TEXT NOT NULL,
                roll_number TEXT NOT NULL,
                section TEXT NOT NULL,
                course TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                dob TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                component_id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_name TEXT NOT NULL,
                total_quantity INTEGER NOT NULL,
                available_quantity INTEGER NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issued_components (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                component_id INTEGER,
                quantity INTEGER NOT NULL,
                issue_date TEXT NOT NULL,
                return_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (component_id) REFERENCES components(component_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                project_name TEXT NOT NULL,
                description TEXT,
                start_date TEXT NOT NULL,
                status TEXT DEFAULT 'ongoing',
                solo_project BOOLEAN DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_date TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_members (
                project_id INTEGER,
                student_id INTEGER,
                join_date TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                PRIMARY KEY (project_id, student_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
        ''')
        
        # Add this new table for chat messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_chat (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER,
                user_role TEXT NOT NULL,
                user_name TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(project_id),
                FOREIGN KEY (user_id) REFERENCES students(student_id)
            )
        ''')
        
        # Add this new table for open chat
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS open_chat (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_role TEXT NOT NULL,
                user_name TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES students(student_id)
            )
        ''')
        conn.commit()

def validate_admission_no(admission_no):
    pattern = r'^[A-Z]{3}\d{4,}$'
    return bool(re.match(pattern, admission_no))

# Add new route for project chat
@app.route('/project_chat/<int:project_id>', methods=['GET', 'POST'])
def project_chat(project_id):
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Check if user has access to this project
        has_access = False
        if session['user_role'] in ['developer', 'teacher', 'attendance_marker']:  # Add teacher here
            has_access = True
        elif session['user_role'] == 'student':
            cursor.execute('''
                SELECT 1 FROM project_members 
                WHERE project_id = ? AND student_id = ?
                UNION
                SELECT 1 FROM projects 
                WHERE project_id = ? AND student_id = ?
            ''', (project_id, session['student_id'], project_id, session['student_id']))
            has_access = cursor.fetchone() is not None
            
        if not has_access:
            flash('Access denied')
            return redirect(url_for('projects'))
            
        # Get project details
        cursor.execute('SELECT project_name FROM projects WHERE project_id = ?', (project_id,))
        project = cursor.fetchone()
        
        if not project:
            flash('Project not found')
            return redirect(url_for('projects'))
            
        # Handle new message
        if request.method == 'POST':
            message = request.form.get('message', '').strip()
            if message:
                user_id = session.get('student_id')
                user_role = session['user_role']
                user_name = ''
                
                if user_role == 'student':
                    cursor.execute('SELECT name FROM students WHERE student_id = ?', (user_id,))
                    user_name = cursor.fetchone()[0]
                else:
                    user_name = user_role.capitalize()
                
                cursor.execute('''
                    INSERT INTO project_chat 
                    (project_id, user_id, user_role, user_name, message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (project_id, user_id, user_role, user_name, message))
                conn.commit()
                
        # Get chat messages
        cursor.execute('''
            SELECT 
                pc.message_id,
                pc.user_name,
                pc.user_role,
                pc.message,
                pc.timestamp
            FROM project_chat pc
            WHERE pc.project_id = ?
            ORDER BY pc.timestamp DESC
            LIMIT 100
        ''', (project_id,))
        messages = cursor.fetchall()
        
    return render_template('project_chat.html',
                         project_id=project_id,
                         project_name=project[0],
                         messages=messages,
                         current_user_role=session['user_role'])

@app.route('/delete_chat_message/<int:message_id>', methods=['POST'])
def delete_chat_message(message_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        flash('Access denied')
        return redirect(url_for('index'))
        
    try:
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            
            # Get project_id before deletion for redirect
            cursor.execute('SELECT project_id FROM project_chat WHERE message_id = ?', (message_id,))
            result = cursor.fetchone()
            
            if result:
                project_id = result[0]
                
                # Delete the message
                cursor.execute('DELETE FROM project_chat WHERE message_id = ?', (message_id,))
                conn.commit()
                
                flash('Message deleted successfully')
                return redirect(url_for('project_chat', project_id=project_id))
            
            flash('Message not found')
            return redirect(request.referrer or url_for('projects'))
            
    except Exception as e:
        app.logger.error(f"Error deleting message {message_id}: {str(e)}")
        flash('Error deleting message. Please try again.')
        return redirect(request.referrer or url_for('projects'))

@app.route('/open_chat', methods=['POST'])
def open_chat():
    if 'user_role' not in session:
        return redirect(url_for('login'))
        
    message = request.form.get('message', '').strip()
    if message:
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            
            user_id = session.get('student_id')
            user_role = session['user_role']
            user_name = ''
            
            if user_role == 'student':
                cursor.execute('SELECT name FROM students WHERE student_id = ?', (user_id,))
                user_name = cursor.fetchone()[0]
            else:
                user_name = user_role.capitalize()
            
            cursor.execute('''
                INSERT INTO open_chat 
                (user_id, user_role, user_name, message)
                VALUES (?, ?, ?, ?)
            ''', (user_id, user_role, user_name, message))
            conn.commit()
            
    return redirect(url_for('index'))

@app.route('/get_open_chat_messages')
def get_open_chat_messages():
    if 'user_role' not in session:
        return jsonify([])
        
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                message_id,
                user_name,
                user_role,
                message,
                strftime('%Y-%m-%d %H:%M:%S', timestamp) as formatted_time
            FROM open_chat
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        messages = [
            {
                'id': row[0],
                'user_name': row[1],
                'user_role': row[2],
                'message': row[3],
                'timestamp': row[4]
            }
            for row in cursor.fetchall()
        ]
        
    return jsonify(messages)

@app.route('/delete_open_chat_message/<int:message_id>', methods=['POST'])
def delete_open_chat_message(message_id):
    if session.get('user_role') not in ['developer', 'teacher']:
        return jsonify({'success': False, 'message': 'Access denied'})
        
    try:
        with sqlite3.connect('attendance.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM open_chat WHERE message_id = ?', (message_id,))
            conn.commit()
            return jsonify({'success': True})
            
    except Exception as e:
        app.logger.error(f"Error deleting message {message_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting message'})

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if session.get('user_role') != 'teacher':
        return redirect(url_for('login'))
    
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        
        # Get chat messages
        cursor.execute('''
            SELECT 
                message_id,
                user_name,
                user_role,
                message,
                timestamp
            FROM open_chat
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        chat_messages = cursor.fetchall()
        
        # Get recent broadcasts
        cursor.execute('''
            SELECT message, created_at, created_by, broadcast_id 
            FROM broadcasts 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        broadcasts = cursor.fetchall()
        
        # Get total students count
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]
        
        # Get today's attendance stats
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN status = 'present' THEN 1 END) as present,
                COUNT(CASE WHEN status = 'absent' THEN 1 END) as absent
            FROM attendance 
            WHERE date = ?
        ''', (today,))
        attendance_stats = cursor.fetchone()
        
    return render_template('teacher_dashboard.html',
                         chat_messages=chat_messages,
                         broadcasts=broadcasts,
                         total_students=total_students,
                         attendance_stats=attendance_stats,
                         current_user_role=session.get('user_role'))

@app.route('/update_attendance', methods=['POST'])
def update_attendance():
    if session.get('user_role') not in ['developer', 'teacher', 'attendance_marker']:
        flash('Access denied')
        return redirect(url_for('index'))
    
    # Implementation of the update_attendance route
    # This is a placeholder and should be implemented based on your requirements
    flash('Update attendance functionality not implemented yet')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Initialize database
    init_db()
    app.run(debug=True, port=5000)
