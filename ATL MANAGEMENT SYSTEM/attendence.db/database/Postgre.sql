-- Create Students table
CREATE TABLE IF NOT EXISTS students (
    student_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    class TEXT NOT NULL,
    roll_number INTEGER NOT NULL,
    section TEXT NOT NULL,
    email TEXT,
    phone_number TEXT,
    address TEXT,
    UNIQUE (roll_number, class, section) -- Optional, ensures uniqueness
);

-- Create Attendance table
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(student_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status TEXT CHECK(status IN ('present', 'absent')) NOT NULL,
    UNIQUE (student_id, date)
);

-- Create Users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('developer', 'attendance_marker')) NOT NULL
);
