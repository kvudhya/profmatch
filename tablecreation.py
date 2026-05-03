import sqlite3
conn = sqlite3.connect("profmatch.db")
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")
#incase already exists
cursor.executescript("""
DROP TABLE IF EXISTS rating;
DROP TABLE IF EXISTS enrollment;
DROP TABLE IF EXISTS section;
DROP TABLE IF EXISTS course;
DROP TABLE IF EXISTS professor;
DROP TABLE IF EXISTS student;
""")

# Creating our tables
cursor.executescript("""
CREATE TABLE student (
    student_id INTEGER PRIMARY KEY,
    student_name_hash TEXT NOT NULL,
    preferred_difficulty REAL,
    interest_level REAL
);

CREATE TABLE professor (
    professor_id INTEGER PRIMARY KEY,
    professor_name TEXT NOT NULL
);

CREATE TABLE course (
    course_id INTEGER PRIMARY KEY,
    course_code TEXT NOT NULL UNIQUE,
    course_name TEXT NOT NULL
);

CREATE TABLE section (
    section_id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL,
    professor_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    year INTEGER NOT NULL,
    FOREIGN KEY (course_id) REFERENCES course(course_id) ON DELETE CASCADE,
    FOREIGN KEY (professor_id) REFERENCES professor(professor_id) ON DELETE CASCADE
);

CREATE TABLE enrollment (
    enrollment_id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    final_grade TEXT,
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES section(section_id) ON DELETE CASCADE,
    UNIQUE (student_id, section_id)
);

CREATE TABLE rating (
    rating_id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES section(section_id) ON DELETE CASCADE,
    UNIQUE (student_id, section_id)
);
""")

