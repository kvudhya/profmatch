

import argparse
import random
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD


#creating the table function.

def create_tables(conn: sqlite3.Connection) -> None:
    """Drop-and-recreate the full schema."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.executescript("""
        DROP TABLE IF EXISTS rating;
        DROP TABLE IF EXISTS enrollment;
        DROP TABLE IF EXISTS section;
        DROP TABLE IF EXISTS course;
        DROP TABLE IF EXISTS professor;
        DROP TABLE IF EXISTS student;
    """)

    cursor.executescript("""
        CREATE TABLE student (
            student_id          INTEGER PRIMARY KEY,
            student_name_hash   TEXT    NOT NULL,
            preferred_difficulty REAL,
            interest_level      REAL
        );

        CREATE TABLE professor (
            professor_id   INTEGER PRIMARY KEY,
            professor_name TEXT    NOT NULL
        );

        CREATE TABLE course (
            course_id   INTEGER PRIMARY KEY,
            course_code TEXT    NOT NULL UNIQUE,
            course_name TEXT    NOT NULL
        );

        CREATE TABLE section (
            section_id   INTEGER PRIMARY KEY,
            course_id    INTEGER NOT NULL,
            professor_id INTEGER NOT NULL,
            semester     TEXT    NOT NULL,
            year         INTEGER NOT NULL,
            FOREIGN KEY (course_id)    REFERENCES course(course_id)       ON DELETE CASCADE,
            FOREIGN KEY (professor_id) REFERENCES professor(professor_id)  ON DELETE CASCADE
        );

        CREATE TABLE enrollment (
            enrollment_id INTEGER PRIMARY KEY,
            student_id    INTEGER NOT NULL,
            section_id    INTEGER NOT NULL,
            final_grade   TEXT,
            FOREIGN KEY (student_id)  REFERENCES student(student_id)   ON DELETE CASCADE,
            FOREIGN KEY (section_id)  REFERENCES section(section_id)   ON DELETE CASCADE,
            UNIQUE (student_id, section_id)
        );

        CREATE TABLE rating (
            rating_id   INTEGER PRIMARY KEY,
            student_id  INTEGER NOT NULL,
            section_id  INTEGER NOT NULL,
            rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            review_text TEXT    NOT NULL,
            FOREIGN KEY (student_id)  REFERENCES student(student_id)  ON DELETE CASCADE,
            FOREIGN KEY (section_id)  REFERENCES section(section_id)  ON DELETE CASCADE,
            UNIQUE (student_id, section_id)
        );
    """)

    conn.commit()
    print("[1/3] Tables created.")




COURSES = [
    (1,  "01:198:111", "Introduction to Computer Science"),
    (2,  "01:198:112", "Data Structures"),
    (3,  "01:198:205", "Introduction to Discrete Structures I"),
    (4,  "01:198:206", "Introduction to Discrete Structures II"),
    (5,  "01:198:210", "Data Management for Data Science"),
    (6,  "01:198:211", "Computer Architecture"),
    (7,  "01:198:213", "Software Methodology"),
    (8,  "01:198:314", "Principles of Programming Languages"),
    (9,  "01:198:336", "Principles of Information and Data Management"),
    (10, "01:198:344", "Design and Analysis of Computer Algorithms"),
]


def _generate_rating(prof_id: int, ratings_df: pd.DataFrame, reviews_df: pd.DataFrame) -> int:
    """
    Derive a 1-5 rating for a (student, professor) pair.

    • > 50 RMP reviews  →  sample from the professor's actual quality_rating
                           distribution captured by the scraper.
    • ≤ 50 RMP reviews  →  sample from N(avg_quality, 1.0) so sparse profiles
                           stay realistic.
    """
    prof_data = ratings_df[ratings_df["section_id"] == prof_id]

    if prof_data.empty:
        sampled = np.random.normal(loc=3.0, scale=1.0)
        return int(np.clip(round(sampled), 1, 5))

    row = prof_data.iloc[0]
    num_ratings = row.get("num_ratings", 0)
    if pd.isna(num_ratings):
        num_ratings = 0

    if num_ratings > 50:
        # Use real per-review quality scores captured by the scraper.
        # Column name: quality_rating  (NOT helpfulness_rating — that column
        # was commented out in seleniumScrapingRating.py and never populated).
        prof_reviews = reviews_df[reviews_df["section_id"] == prof_id]
        valid = prof_reviews["quality_rating"].dropna().tolist()

        if valid:
            sampled = float(np.random.choice(valid))
            return int(np.clip(round(sampled), 1, 5))

    # Fallback: normal distribution centred on the professor's RMP quality score.
    quality = row.get("quality", 3.0)
    if pd.isna(quality):
        quality = 3.0

    sampled = np.random.normal(loc=quality, scale=1.0)
    return int(np.clip(round(sampled), 1, 5))


def _get_review_text(prof_id: int, reviews_df: pd.DataFrame, global_pool: list[str]) -> str:
    mask = (reviews_df["section_id"] == prof_id) & reviews_df["review_text"].notna()
    prof_reviews = reviews_df[mask]["review_text"].tolist()

    if prof_reviews:
        return random.choice(prof_reviews)
    return random.choice(global_pool)


def populate_database(
    conn: sqlite3.Connection,
    ratings_csv: str | Path,
    reviews_csv: str | Path,
    num_students: int = 150,
    sections_per_professor: int = 3,
    extra_synthetic_ratings: int = 400,
) -> None:

    ratings_csv = Path(ratings_csv)
    reviews_csv = Path(reviews_csv)

    if not ratings_csv.exists():
        raise FileNotFoundError(f"Ratings CSV not found: {ratings_csv}")
    if not reviews_csv.exists():
        raise FileNotFoundError(f"Reviews CSV not found: {reviews_csv}")

    ratings_df = pd.read_csv(ratings_csv)
    reviews_df = pd.read_csv(reviews_csv)

    global_pool = reviews_df["review_text"].dropna().tolist()
    if not global_pool:
        global_pool = ["No review available."]  # last-resort sentinel

    cursor = conn.cursor()

    # ── Professors ────────────────────────────────────────────────────────────
    professor_map: dict[int, str] = {}   # prof_id → name
    for _, row in ratings_df.iterrows():
        prof_id = int(row["section_id"])
        name = row.get("rutgers_name")
        if pd.isna(name) or not str(name).strip():
            continue
        professor_map[prof_id] = str(name).strip()
        cursor.execute(
            "INSERT OR IGNORE INTO professor (professor_id, professor_name) VALUES (?, ?)",
            (prof_id, professor_map[prof_id]),
        )

    # ── Courses ───────────────────────────────────────────────────────────────
    for course in COURSES:
        cursor.execute(
            "INSERT OR IGNORE INTO course (course_id, course_code, course_name) VALUES (?, ?, ?)",
            course,
        )

    # ── Sections (n per professor, random course + semester) ─────────────────
    section_id = 1
    professor_sections: dict[int, list[int]] = {}
    for prof_id in professor_map:
        professor_sections[prof_id] = []
        for _ in range(sections_per_professor):
            course_id = random.randint(1, len(COURSES))
            semester  = random.choice(["Fall", "Spring"])
            year      = random.choice([2024, 2025, 2026])
            cursor.execute(
                "INSERT OR IGNORE INTO section "
                "(section_id, course_id, professor_id, semester, year) VALUES (?, ?, ?, ?, ?)",
                (section_id, course_id, prof_id, semester, year),
            )
            professor_sections[prof_id].append(section_id)
            section_id += 1

    # ── Students ──────────────────────────────────────────────────────────────
    for student_id in range(1, num_students + 1):
        cursor.execute(
            "INSERT OR IGNORE INTO student "
            "(student_id, student_name_hash, preferred_difficulty, interest_level) "
            "VALUES (?, ?, ?, ?)",
            (
                student_id,
                f"student_hash_{student_id}",
                round(random.uniform(1.0, 5.0), 2),
                round(random.uniform(1.0, 5.0), 2),
            ),
        )

    # ── Enrollments + Ratings ─────────────────────────────────────────────────
    all_prof_ids   = list(professor_map.keys())
    enrollment_id  = 1
    rating_id      = 1
    seen_pairs: set[tuple[int, int]] = set()

    total_to_gen = len(all_prof_ids) * 5 + extra_synthetic_ratings

    for _ in range(total_to_gen):
        student_id     = random.randint(1, num_students)
        prof_id        = random.choice(all_prof_ids)
        sec_id         = random.choice(professor_sections[prof_id])

        pair = (student_id, sec_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        final_grade = random.choice([None, "A", "B+", "B", "C+", "C"])
        cursor.execute(
            "INSERT OR IGNORE INTO enrollment "
            "(enrollment_id, student_id, section_id, final_grade) VALUES (?, ?, ?, ?)",
            (enrollment_id, student_id, sec_id, final_grade),
        )
        enrollment_id += 1

        rating_val  = _generate_rating(prof_id, ratings_df, reviews_df)
        review_text = _get_review_text(prof_id, reviews_df, global_pool)

        cursor.execute(
            "INSERT OR IGNORE INTO rating "
            "(rating_id, student_id, section_id, rating, review_text) VALUES (?, ?, ?, ?, ?)",
            (rating_id, student_id, sec_id, rating_val, review_text),
        )
        rating_id += 1

    conn.commit()

    print("[2/3] Database populated.")
    print(f"      Professors : {len(professor_map)}")
    print(f"      Students   : {num_students}")
    print(f"      Ratings    : {rating_id - 1}")


#Model class initally developed to use in accordance with content based learning.

class ProfessorRecommender:
    """
    Collaborative-filter recommender built on mean-centred TruncatedSVD.

    Mean-centring removes per-student rating bias before factorisation, so a
    student who rates everyone 4/5 doesn't drown out signal from their relative
    preferences.
    """

    def __init__(self, conn: sqlite3.Connection, n_components: int | None = None) -> None:
        self.conn = conn
        self._train(n_components)

    def _train(self, n_components: int | None) -> None:
        query = """
            SELECT r.student_id,
                   p.professor_id,
                   p.professor_name,
                   r.rating
            FROM   rating r
            JOIN   section   s ON r.section_id   = s.section_id
            JOIN   professor p ON s.professor_id  = p.professor_id
            ORDER  BY r.student_id, p.professor_id
        """
        df = pd.read_sql(query, self.conn)

        if df.empty:
            raise ValueError("No rating data found in the database.")

        # Build student × professor interaction matrix
        self.interaction_matrix = df.pivot_table(
            index="student_id",
            columns="professor_id",
            values="rating",
            aggfunc="mean",
        )

        # Mean-centre per student, fill missing with 0
        self.student_means = self.interaction_matrix.mean(axis=1)
        centred = self.interaction_matrix.sub(self.student_means, axis=0).fillna(0)

        # Choose number of latent factors safely
        max_components = min(centred.shape) - 1
        k = n_components if n_components else min(10, max_components)
        k = max(1, min(k, max_components))

        svd = TruncatedSVD(n_components=k, random_state=42)
        student_latent = svd.fit_transform(centred)

        # Reconstruct and un-centre
        predicted_centred = student_latent @ svd.components_
        predicted = predicted_centred + self.student_means.values.reshape(-1, 1)
        predicted = np.clip(predicted, 1, 5)

        self.predicted_df = pd.DataFrame(
            predicted,
            index=self.interaction_matrix.index,
            columns=self.interaction_matrix.columns,
        )

        self.professor_lookup: dict[int, str] = dict(
            pd.read_sql("SELECT professor_id, professor_name FROM professor", self.conn).values
        )

        explained = svd.explained_variance_ratio_.sum() #we get culmulitive explained variance
        print(f"[3/3] SVD model trained  (k={k}, explained variance={explained:.1%}).")

    def recommend(self, student_id: int, top_n: int = 5) -> pd.DataFrame:
        """
        Return the top-N unrated professors for a given student,
        sorted by predicted rating descending.
        """
        if student_id not in self.predicted_df.index:
            print(f"Student {student_id} has no ratings in the DB.")
            return pd.DataFrame(columns=["professor_id", "professor_name", "predicted_rating"])

        actual      = self.interaction_matrix.loc[student_id]
        unrated     = actual[actual.isna()].index
        predictions = self.predicted_df.loc[student_id, unrated].sort_values(ascending=False)

        rec = pd.DataFrame({
            "professor_id"    : predictions.index,
            "predicted_rating": predictions.values.round(2),
        })
        rec["professor_name"] = rec["professor_id"].map(self.professor_lookup)
        return rec[["professor_id", "professor_name", "predicted_rating"]].head(top_n)




def main() -> None:
    parser = argparse.ArgumentParser(description="CSV → SQLite → SVD pipeline")
    parser.add_argument("--ratings",      default="Data/rutgers_cs_rmp_ratings.csv",
                        help="Path to the professor-level ratings CSV from the scraper")
    parser.add_argument("--reviews",      default="Data/rutgers_cs_rmp_reviews.csv",
                        help="Path to the per-review CSV from the scraper")
    parser.add_argument("--db",           default="profmatch.db",
                        help="SQLite database file to create/overwrite")
    parser.add_argument("--students",     type=int, default=150,
                        help="Number of synthetic student accounts to generate")
    parser.add_argument("--sections",     type=int, default=3,
                        help="Number of sections to create per professor")
    parser.add_argument("--extra",        type=int, default=400,
                        help="Extra synthetic rating rows beyond the base coverage pass")
    parser.add_argument("--demo-student", type=int, default=1,
                        help="Student ID to print example recommendations for")
    parser.add_argument("--top-n",        type=int, default=5,
                        help="How many recommendations to show")
    args = parser.parse_args()

    db_path = Path(args.db)
    print(f"\n{'='*60}")
    print(f"  ProfMatch Pipeline")
    print(f"  DB       : {db_path}")
    print(f"  Ratings  : {args.ratings}")
    print(f"  Reviews  : {args.reviews}")
    print(f"{'='*60}\n")

    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        populate_database(
            conn,
            ratings_csv=args.ratings,
            reviews_csv=args.reviews,
            num_students=args.students,
            sections_per_professor=args.sections,
            extra_synthetic_ratings=args.extra,
        )
        recommender = ProfessorRecommender(conn,n_components=15)

        print(f"\nTop-{args.top_n} recommendations for student {args.demo_student}:")
        recs = recommender.recommend(args.demo_student, top_n=args.top_n)
        if recs.empty:
            print("  (no recommendations — student may have rated all professors)")
        else:
            print(recs.to_string(index=False))
    finally:
        conn.close()

    print(f"\nDone. Database written to: {db_path.resolve()}")


if __name__ == "__main__":
    main()
