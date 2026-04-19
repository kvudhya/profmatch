# %% [markdown]
# # ProfMatch - Notebook Version
# This notebook is designed to run top-to-bottom in Jupyter or GitHub notebooks.
# It uses three data source levels in this order:
# 1. Live scraping from direct professor URLs if you add them
# 2. Local CSV files if they exist
# 3. Built-in sample data so the notebook always runs

# %%


# %% [markdown]
# ## 3. Try live scraping for professor pages

# %% [markdown]
# ## 4. Try live scraping for Rutgers course pages

# %%
course_material_rows = []

for idx, url in enumerate(COURSE_MATERIAL_URLS, start=1):
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = clean_text(soup.get_text(" ", strip=True))

        course_material_rows.append(
            {
                "prof_id": idx,
                "extracted_text": page_text[:5000],
            }
        )
    except requests.RequestException as exc:
        print(f"Failed to fetch {url}: {exc}")

scraped_course_materials_df = pd.DataFrame(course_material_rows)

print(f"Scraped course material rows: {len(scraped_course_materials_df)}")


# %% [markdown]
# ## 5. Load CSV files if they exist

# %%
if os.path.exists("professors.csv"):
    csv_professors_df = pd.read_csv("professors.csv")
else:
    csv_professors_df = pd.DataFrame()

if os.path.exists("reviews.csv"):
    csv_reviews_df = pd.read_csv("reviews.csv")
else:
    csv_reviews_df = pd.DataFrame()

if os.path.exists("course_materials.csv"):
    csv_course_materials_df = pd.read_csv("course_materials.csv")
else:
    csv_course_materials_df = pd.DataFrame()

if os.path.exists("student_profiles.csv"):
    student_profiles_df = pd.read_csv("student_profiles.csv")
else:
    student_profiles_df = pd.DataFrame(
        [
            {
                "student_id": 1,
                "gpa_range": "3.5-4.0",
                "major": "Computer Science",
                "credit_load": 15,
                "workload_tolerance": 2,
                "grade_goal": "A",
                "learning_style_tag": "Visual",
            }
        ]
    )

if os.path.exists("student_professor_ratings.csv"):
    interaction_data = pd.read_csv("student_professor_ratings.csv")
else:
    interaction_data = pd.DataFrame()

print(f"CSV professor rows: {len(csv_professors_df)}")
print(f"CSV review rows: {len(csv_reviews_df)}")
print(f"CSV course material rows: {len(csv_course_materials_df)}")


# %% [markdown]
# ## 6. Built-in fallback data so the notebook always runs

# %%
fallback_professors_df = pd.DataFrame(
    [
        {
            "prof_id": 1,
            "name": "Professor A",
            "department": "Computer Science",
            "rmp_rating": 4.8,
            "rmp_difficulty": 2.1,
            "would_take_again_pct": 91,
        },
        {
            "prof_id": 2,
            "name": "Professor B",
            "department": "Computer Science",
            "rmp_rating": 4.1,
            "rmp_difficulty": 3.4,
            "would_take_again_pct": 72,
        },
        {
            "prof_id": 3,
            "name": "Professor C",
            "department": "Mathematics",
            "rmp_rating": 3.5,
            "rmp_difficulty": 4.3,
            "would_take_again_pct": 54,
        },
    ]
)

fallback_reviews_df = pd.DataFrame(
    [
        {"prof_id": 1, "review_text": "clear lectures helpful exams project based learning fair grading"},
        {"prof_id": 1, "review_text": "great slides approachable professor coding assignments were manageable"},
        {"prof_id": 2, "review_text": "good lecturer but workload is moderate and exams can be tricky"},
        {"prof_id": 3, "review_text": "very difficult homework proof heavy class and hard exams"},
    ]
)

fallback_course_materials_df = pd.DataFrame(
    [
        {"prof_id": 1, "extracted_text": "weekly coding assignments lecture slides quizzes and project checkpoints"},
        {"prof_id": 2, "extracted_text": "programming projects midterm exam final exam object oriented design"},
        {"prof_id": 3, "extracted_text": "theorems derivations proofs problem sets long written exams"},
    ]
)


# %% [markdown]
# ## 7. Choose the best available professor data

# %%
if not scraped_professors_df.empty:
    professors_df = scraped_professors_df.copy()
    reviews_df = scraped_reviews_df.copy()
    data_source_used = "live professor scrape"
elif not csv_professors_df.empty:
    professors_df = csv_professors_df.copy()
    reviews_df = csv_reviews_df.copy()
    data_source_used = "local CSV files"
else:
    professors_df = fallback_professors_df.copy()
    reviews_df = fallback_reviews_df.copy()
    data_source_used = "built-in sample data"

if not scraped_course_materials_df.empty:
    course_materials_df = scraped_course_materials_df.copy()
elif not csv_course_materials_df.empty:
    course_materials_df = csv_course_materials_df.copy()
else:
    course_materials_df = fallback_course_materials_df.copy()

print(f"Using professor data source: {data_source_used}")
print(f"Final professor rows: {len(professors_df)}")
print(f"Final review rows: {len(reviews_df)}")
print(f"Final course material rows: {len(course_materials_df)}")


# %% [markdown]
# ## 8. Clean and prepare data

# %%
for col in ["prof_id", "name", "department", "rmp_rating", "rmp_difficulty", "would_take_again_pct"]:
    if col not in professors_df.columns:
        professors_df[col] = np.nan

for col in ["prof_id", "review_text"]:
    if col not in reviews_df.columns:
        reviews_df[col] = ""

for col in ["prof_id", "extracted_text"]:
    if col not in course_materials_df.columns:
        course_materials_df[col] = ""

professors_df["name"] = professors_df["name"].fillna("Unknown Professor").astype(str)
professors_df["department"] = professors_df["department"].fillna("Unknown Department").astype(str)
professors_df["rmp_rating"] = pd.to_numeric(professors_df["rmp_rating"], errors="coerce")
professors_df["rmp_difficulty"] = pd.to_numeric(professors_df["rmp_difficulty"], errors="coerce")
professors_df["would_take_again_pct"] = pd.to_numeric(professors_df["would_take_again_pct"], errors="coerce")

professors_df["rmp_rating"] = professors_df["rmp_rating"].fillna(professors_df["rmp_rating"].mean())
professors_df["rmp_difficulty"] = professors_df["rmp_difficulty"].fillna(professors_df["rmp_difficulty"].mean())
professors_df["would_take_again_pct"] = professors_df["would_take_again_pct"].fillna(0)

if professors_df["rmp_rating"].isna().all():
    professors_df["rmp_rating"] = 0.0
if professors_df["rmp_difficulty"].isna().all():
    professors_df["rmp_difficulty"] = 0.0

reviews_df["review_text"] = reviews_df["review_text"].fillna("").astype(str)
course_materials_df["extracted_text"] = course_materials_df["extracted_text"].fillna("").astype(str)

review_text_grouped = reviews_df.groupby("prof_id", dropna=False)["review_text"].apply(
    lambda values: " ".join(clean_text(v) for v in values if clean_text(v))
).reset_index()

course_text_grouped = course_materials_df.groupby("prof_id", dropna=False)["extracted_text"].apply(
    lambda values: " ".join(clean_text(v) for v in values if clean_text(v))
).reset_index()

professor_profiles = professors_df[
    ["prof_id", "name", "department", "rmp_rating", "rmp_difficulty", "would_take_again_pct"]
].copy()

professor_profiles = professor_profiles.merge(review_text_grouped, on="prof_id", how="left")
professor_profiles = professor_profiles.merge(course_text_grouped, on="prof_id", how="left")
professor_profiles["review_text"] = professor_profiles["review_text"].fillna("")
professor_profiles["extracted_text"] = professor_profiles["extracted_text"].fillna("")
professor_profiles["combined_text"] = (
    professor_profiles["review_text"] + " " + professor_profiles["extracted_text"]
).str.strip()
professor_profiles.loc[professor_profiles["combined_text"] == "", "combined_text"] = "no review text available"

professor_profiles.head()


# %% [markdown]
# ## 9. Build recommendation model

# %%
sample_student = {
    "preferred_difficulty": 2.5,
    "preferred_rating": 4.5,
    "preferred_take_again_pct": 80,
    "preferred_keywords": "easy grading clear lectures helpful exams project based learning",
}

vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
tfidf_matrix = vectorizer.fit_transform(professor_profiles["combined_text"])

numerical_features = professor_profiles[["rmp_rating", "rmp_difficulty", "would_take_again_pct"]].copy()
scaler = MinMaxScaler()
scaled_numerical = scaler.fit_transform(numerical_features)

final_professor_features = np.hstack([tfidf_matrix.toarray(), scaled_numerical])

student_text_vector = vectorizer.transform([clean_text(sample_student["preferred_keywords"])]).toarray()
student_numerical_input = pd.DataFrame(
    [
        {
            "rmp_rating": safe_float(sample_student["preferred_rating"]),
            "rmp_difficulty": safe_float(sample_student["preferred_difficulty"]),
            "would_take_again_pct": safe_float(sample_student["preferred_take_again_pct"]),
        }
    ]
)
student_numerical = scaler.transform(student_numerical_input)

student_vector = np.hstack([student_text_vector, student_numerical])
similarity_scores = cosine_similarity(student_vector, final_professor_features)[0]

professor_profiles["recommendation_score"] = similarity_scores
recommended_professors = professor_profiles.sort_values(by="recommendation_score", ascending=False).reset_index(drop=True)
recommended_professors.head(10)


# %% [markdown]
# ## 10. Optional collaborative filtering with SVD

# %%
latent_matrix = None

if not interaction_data.empty and {"student_id", "prof_id", "rating"}.issubset(interaction_data.columns):
    interaction_matrix = interaction_data.pivot_table(
        index="student_id",
        columns="prof_id",
        values="rating",
        aggfunc="mean",
    ).fillna(0)

    if interaction_matrix.shape[0] >= 2 and interaction_matrix.shape[1] >= 2:
        n_components = min(5, min(interaction_matrix.shape) - 1)
        if n_components >= 1:
            svd = TruncatedSVD(n_components=n_components, random_state=42)
            latent_matrix = svd.fit_transform(interaction_matrix)
            print("Latent Student Feature Matrix Shape:", latent_matrix.shape)
        else:
            print("Skipping SVD: not enough dimensions.")
    else:
        print("Skipping SVD: need at least 2 students and 2 professors.")
else:
    print("Skipping SVD: no valid interaction data found.")


# %% [markdown]
# ## 11. Save output

# %%
recommended_professors.to_csv(OUTPUT_FILE, index=False)
print(f"Recommendation results saved to {OUTPUT_FILE}")


# %% [markdown]
# ## 12. Tests

# %%
class TestProfMatchNotebook(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  hello   world  "), "hello world")
        self.assertEqual(clean_text(None), "")

    def test_safe_float(self):
        self.assertEqual(safe_float("4.5"), 4.5)
        self.assertEqual(safe_float("4.5/5"), 4.5)
        self.assertEqual(safe_float("abc", default=1.2), 1.2)

    def test_safe_percentage(self):
        self.assertEqual(safe_percentage("85%"), 85.0)
        self.assertEqual(safe_percentage(None, default=10.0), 10.0)

    def test_fallback_professor_data_exists(self):
        self.assertFalse(fallback_professors_df.empty)
        self.assertIn("name", fallback_professors_df.columns)

    def test_final_professor_data_exists(self):
        self.assertFalse(professors_df.empty)
        self.assertIn("name", professors_df.columns)

    def test_recommendation_output_exists(self):
        self.assertFalse(recommended_professors.empty)
        self.assertIn("recommendation_score", recommended_professors.columns)

    def test_top_result_has_name(self):
        self.assertTrue(isinstance(recommended_professors.iloc[0]["name"], str))
        self.assertTrue(len(recommended_professors.iloc[0]["name"]) > 0)

    def test_no_missing_combined_text(self):
        self.assertFalse(professor_profiles["combined_text"].isna().any())

    def test_output_file_name(self):
        self.assertEqual(OUTPUT_FILE, "recommended_professors_output.csv")

suite = unittest.TestLoader().loadTestsFromTestCase(TestProfMatchNotebook)
unittest.TextTestRunner(verbosity=2).run(suite)
