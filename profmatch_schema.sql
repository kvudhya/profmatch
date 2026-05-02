-- Drop tables in dependency order if they already exist
DROP TABLE IF EXISTS rating;
DROP TABLE IF EXISTS enrollment;
DROP TABLE IF EXISTS section;
DROP TABLE IF EXISTS course;
DROP TABLE IF EXISTS professor;
DROP TABLE IF EXISTS student;

-- =========================
-- 1. Student
-- =========================
CREATE TABLE student (
    student_id          INT PRIMARY KEY,
    student_name_hash   VARCHAR(255) NOT NULL,
    preferred_difficulty NUMERIC(3,2),
    interest_level      NUMERIC(3,2)
);

-- =========================
-- 2. Professor
-- =========================
CREATE TABLE professor (
    professor_id        INT PRIMARY KEY,
    professor_name      VARCHAR(255) NOT NULL
);

-- =========================
-- 3. Course
-- =========================
CREATE TABLE course (
    course_id           INT PRIMARY KEY,
    course_code         VARCHAR(50) NOT NULL UNIQUE,
    course_name         VARCHAR(255) NOT NULL
);

-- =========================
-- 4. Section
-- One professor teaches one course in one term/section
-- =========================
CREATE TABLE section (
    section_id          INT PRIMARY KEY,
    course_id           INT NOT NULL,
    professor_id        INT NOT NULL,
    semester            VARCHAR(20) NOT NULL,
    year                INT NOT NULL,

    CONSTRAINT fk_section_course
        FOREIGN KEY (course_id)
        REFERENCES course(course_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_section_professor
        FOREIGN KEY (professor_id)
        REFERENCES professor(professor_id)
        ON DELETE CASCADE
);

-- =========================
-- 5. Enrollment
-- connects student to section and stores outcome
-- =========================
CREATE TABLE enrollment (
    enrollment_id       INT PRIMARY KEY,
    student_id          INT NOT NULL,
    section_id          INT NOT NULL,
    final_grade         VARCHAR(5),

    CONSTRAINT fk_enrollment_student
        FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_enrollment_section
        FOREIGN KEY (section_id)
        REFERENCES section(section_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_enrollment UNIQUE (student_id, section_id)
);

-- =========================
-- 6. Rating
-- connects student to section for SVD interaction matrix
-- =========================
CREATE TABLE rating (
    rating_id           INT PRIMARY KEY,
    student_id          INT NOT NULL,
    section_id          INT NOT NULL,
    rating              INT NOT NULL CHECK (rating BETWEEN 1 AND 5),

    CONSTRAINT fk_rating_student
        FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_rating_section
        FOREIGN KEY (section_id)
        REFERENCES section(section_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_rating UNIQUE (student_id, section_id)
);