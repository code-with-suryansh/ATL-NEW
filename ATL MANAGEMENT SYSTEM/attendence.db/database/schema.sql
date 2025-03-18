-- Create Students table
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    class TEXT NOT NULL,
    roll_number INTEGER NOT NULL,
    section TEXT NOT NULL,
    email TEXT,
    phone_number TEXT,
    address TEXT
);

-- Create Attendance table
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    date DATE NOT NULL,
    status TEXT CHECK(status IN ('present', 'absent')) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(student_id, date)
);


CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('developer', 'attendance_marker')) NOT NULL
); 