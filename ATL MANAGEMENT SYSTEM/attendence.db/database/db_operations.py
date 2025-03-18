import sqlite3
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self):
        self.db_path = 'attendance.db'
        
    def get_connection(self):
        return sqlite3.connect(self.db_path)
        
    def add_student(self, admission_no, name, fathers_name, mothers_name,
                    class_name, roll_number, section, course,
                    email=None, phone=None, address=None, dob=None, password=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if admission number already exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE admission_no = ?', 
                             (admission_no,))
                if cursor.fetchone()[0] > 0:
                    return False
                
                cursor.execute('''
                    INSERT INTO students (
                        admission_no, name, fathers_name, mothers_name,
                        class, roll_number, section, course,
                        email, phone, address, dob, password
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (admission_no, name, fathers_name, mothers_name,
                      class_name, roll_number, section, course,
                      email, phone, address, dob, password))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error adding student: {e}")
            return False
            
    def mark_attendance(self, student_id, date, status):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if attendance already marked
                cursor.execute('''
                    SELECT COUNT(*) FROM attendance 
                    WHERE student_id = ? AND date = ?
                ''', (student_id, date))
                
                if cursor.fetchone()[0] > 0:
                    return False, "Attendance already marked for this date"
                
                cursor.execute('''
                    INSERT INTO attendance (student_id, date, status)
                    VALUES (?, ?, ?)
                ''', (student_id, date, status))
                
                conn.commit()
                return True, "Attendance marked successfully"
                
        except Exception as e:
            return False, str(e)
            
    def get_student_details(self, student_id=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if student_id:
                cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
                return cursor.fetchone()
            else:
                cursor.execute('SELECT * FROM students')
                return cursor.fetchall()
                
    def get_student_attendance(self, student_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, status 
                FROM attendance 
                WHERE student_id = ?
                ORDER BY date DESC
            ''', (student_id,))
            return cursor.fetchall()
            
    def get_attendance_by_date_range(self, start_date=None, end_date=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if start_date and end_date:
                cursor.execute('''
                    SELECT s.name, s.class, s.roll_number, s.section, a.date, a.status
                    FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    WHERE a.date BETWEEN ? AND ?
                    ORDER BY a.date DESC, s.name
                ''', (start_date, end_date))
            else:
                cursor.execute('''
                    SELECT s.name, s.class, s.roll_number, s.section, a.date, a.status
                    FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    ORDER BY a.date DESC, s.name
                ''')
            return cursor.fetchall()
            
    def get_students_without_attendance(self, date):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM students s
                WHERE NOT EXISTS (
                    SELECT 1 FROM attendance a 
                    WHERE a.student_id = s.student_id 
                    AND a.date = ?
                )
            ''', (date,))
            return cursor.fetchall()
            
    def delete_student(self, student_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First delete related records
                cursor.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
                cursor.execute('DELETE FROM issued_components WHERE student_id = ?', (student_id,))
                cursor.execute('DELETE FROM projects WHERE student_id = ?', (student_id,))
                
                # Then delete the student
                cursor.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
                
                conn.commit()
                return True, "Student deleted successfully"
                
        except Exception as e:
            return False, str(e)