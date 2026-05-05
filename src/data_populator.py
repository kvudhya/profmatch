import random
import sqlite3
import pandas as pd


def realistic_review_fallback():
    reviews = [
        "Good professor, lectures were clear.",
        "Class was hard but fair.",
        "Exams were difficult but manageable.",
        "Helpful if you go to office hours.",
        "Lectures were confusing sometimes.",
        "Good class overall.",
        "The workload was heavy.",
        "Professor explained concepts well.",
        "Not an easy class but I learned a lot.",
        "Assignments took a lot of time."
    ]
    return random.choice(reviews)


def score_to_rating(score):
    """
    Convert Reddit score into a rough 1-5 rating.
    This is not perfect, but gives us a realistic synthetic signal.
    """
    if pd.isna(score):
        return random.randint(2, 5)

    try:
        score = int(score)
    except:
        return random.randint(2, 5)

    if score <= 0:
        return random.choice([1, 2])
    elif score <= 3:
        return random.choice([2, 3])
    elif score <= 10:
        return random.choice([3, 4])
    else:
        return random.choice([4, 5])


def populate_from_reddit_for_svd(
    conn,
    reddit_csv_path,
    num_students=120,
    sections_per_professor=3,
    extra_synthetic_ratings=300
):
    cursor = conn.cursor()

    reddit_df = pd.read_csv(reddit_csv_path)

    # Keep rows with professor names
    reddit_df = reddit_df.dropna(subset=["professor_name"])

    professor_names = sorted(reddit_df["professor_name"].unique())

    professor_map = {}
    professor_sections = {}

    # -------------------------
    # 1. Insert real professors
    # -------------------------
    for professor_id, name in enumerate(professor_names, start=1):
        professor_map[name] = professor_id

        cursor.execute("""
            INSERT OR IGNORE INTO professor (professor_id, professor_name)
            VALUES (?, ?)
        """, (professor_id, name))

    # -------------------------
    # 2. Insert fake CS courses
    # -------------------------
    courses = [
        (1, "01:198:111", "Introduction to Computer Science"),
        (2, "01:198:112", "Data Structures"),
        (3, "01:198:205", "Introduction to Discrete Structures I"),
        (4, "01:198:206", "Introduction to Discrete Structures II"),
        (5, "01:198:210", "Data Management for Data Science"),
        (6, "01:198:211", "Computer Architecture"),
        (7, "01:198:213", "Software Methodology"),
        (8, "01:198:314", "Principles of Programming Languages"),
        (9, "01:198:336", "Principles of Information and Data Management"),
        (10, "01:198:344", "Design and Analysis of Computer Algorithms")
    ]

    for course in courses:
        cursor.execute("""
            INSERT OR IGNORE INTO course (course_id, course_code, course_name)
            VALUES (?, ?, ?)
        """, course)

    # -------------------------
    # 3. Create sections for each professor
    # -------------------------
    section_id = 1

    for professor_name, professor_id in professor_map.items():
        professor_sections[professor_id] = []

        for _ in range(sections_per_professor):
            course_id = random.randint(1, len(courses))
            semester = random.choice(["Fall", "Spring"])
            year = random.choice([2024, 2025, 2026])

            cursor.execute("""
                INSERT OR IGNORE INTO section
                (section_id, course_id, professor_id, semester, year)
                VALUES (?, ?, ?, ?, ?)
            """, (section_id, course_id, professor_id, semester, year))

            professor_sections[professor_id].append(section_id)
            section_id += 1

    # -------------------------
    # 4. Insert students
    # -------------------------
    for student_id in range(1, num_students + 1):
        preferred_difficulty = random.choice([
            None,
            round(random.uniform(1.0, 5.0), 2)
        ])

        interest_level = random.choice([
            None,
            round(random.uniform(1.0, 5.0), 2)
        ])

        cursor.execute("""
            INSERT OR IGNORE INTO student
            (student_id, student_name_hash, preferred_difficulty, interest_level)
            VALUES (?, ?, ?, ?)
        """, (
            student_id,
            f"student_hash_{student_id}",
            preferred_difficulty,
            interest_level
        ))

    enrollment_id = 1
    rating_id = 1

    used_student_section_pairs = set()

    # -------------------------
    # 5. Insert real Reddit-based ratings
    # -------------------------
    for _, row in reddit_df.iterrows():
        professor_name = row["professor_name"]
        professor_id = professor_map.get(professor_name)

        if professor_id is None:
            continue

        section_id_for_prof = random.choice(professor_sections[professor_id])
        student_id = random.randint(1, num_students)

        pair = (student_id, section_id_for_prof)

        if pair in used_student_section_pairs:
            continue

        used_student_section_pairs.add(pair)

        final_grade = random.choice([
            None, None,
            "A", "B+", "B", "C+", "C"
        ])

        cursor.execute("""
            INSERT OR IGNORE INTO enrollment
            (enrollment_id, student_id, section_id, final_grade)
            VALUES (?, ?, ?, ?)
        """, (
            enrollment_id,
            student_id,
            section_id_for_prof,
            final_grade
        ))

        enrollment_id += 1

        review_text = ""

        if "snippet" in reddit_df.columns:
            review_text = str(row.get("snippet", "")).strip()

        if not review_text or review_text.lower() == "nan":
            review_text = realistic_review_fallback()

        score = row.get("score") if "score" in reddit_df.columns else None
        rating = score_to_rating(score)

        cursor.execute("""
            INSERT OR IGNORE INTO rating
            (rating_id, student_id, section_id, rating, review_text)
            VALUES (?, ?, ?, ?, ?)
        """, (
            rating_id,
            student_id,
            section_id_for_prof,
            rating,
            review_text
        ))

        rating_id += 1

    # -------------------------
    # 6. Add extra synthetic ratings for overlap
    # -------------------------
    all_professor_ids = list(professor_sections.keys())

    for _ in range(extra_synthetic_ratings):
        student_id = random.randint(1, num_students)

        # each synthetic rating connects to a professor's real section
        professor_id = random.choice(all_professor_ids)
        section_id_for_prof = random.choice(professor_sections[professor_id])

        pair = (student_id, section_id_for_prof)

        if pair in used_student_section_pairs:
            continue

        used_student_section_pairs.add(pair)

        final_grade = random.choice([
            None, None,
            "A", "A-", "B+", "B", "C+", "C"
        ])

        cursor.execute("""
            INSERT OR IGNORE INTO enrollment
            (enrollment_id, student_id, section_id, final_grade)
            VALUES (?, ?, ?, ?)
        """, (
            enrollment_id,
            student_id,
            section_id_for_prof,
            final_grade
        ))

        enrollment_id += 1

        rating = random.randint(1, 5)

        review_text = random.choice([
            realistic_review_fallback(),
            realistic_review_fallback(),
            "ok",
            "good",
            "hard",
            "not bad"
        ])

        cursor.execute("""
            INSERT OR IGNORE INTO rating
            (rating_id, student_id, section_id, rating, review_text)
            VALUES (?, ?, ?, ?, ?)
        """, (
            rating_id,
            student_id,
            section_id_for_prof,
            rating,
            review_text
        ))

        rating_id += 1

    conn.commit()

    print("Database populated for SVD successfully.")
    print(f"Professors inserted: {len(professor_names)}")
    print(f"Students inserted: {num_students}")
    print(f"Sections inserted: {section_id - 1}")
    print(f"Ratings attempted: {rating_id - 1}")