# ProfMatch: Rutgers CS Professor Recommendation System

ProfMatch is a CS 210 data-management project that builds a Rutgers Computer Science professor recommendation system. The project scrapes professor ratings from Rate My Professors, stores professor/course/student/rating data in a normalized SQLite database, generates synthetic student interactions, trains an SVD-based collaborative-filtering recommender, and creates report-ready visualizations.

## Project Overview

The goal of ProfMatch is to help students discover professors they may prefer based on historical rating patterns. The system combines real professor/review data with synthetic student enrollment and rating records to create a student-professor interaction matrix. A Singular Value Decomposition (SVD) model is then used to predict which unrated professors a student may rate highly.

### Main Workflow

```text
Rate My Professors scraping
        ↓
Professor + review CSV files
        ↓
SQLite relational database
        ↓
Synthetic students, sections, enrollments, and ratings
        ↓
Student × professor interaction matrix
        ↓
SVD recommendation model
        ↓
Professor recommendations + visualizations
```

## Repository Structure

```text
.
├── pipeline.py                    # Full CSV → SQLite → SVD recommendation pipeline
├── seleniumScrapingRating.py       # Selenium/BeautifulSoup scraper for RMP data
├── visualizations.py               # Generates figures from profmatch.db
├── profmatch.db                    # SQLite database generated/used by the project
├── Data/                           # Expected location for generated CSV files
│   ├── rutgers_cs_rmp_ratings.csv
│   └── rutgers_cs_rmp_reviews.csv
├── figures/                        # Output folder for generated charts
└── README.md
```

> Note: `seleniumScrapingRating.py` imports helper functions from `utils.utils`, including `clean_text`, `get_rutgers_cs_professors`, `DEFAULT_HEADERS`, and `DEFAULT_TIMEOUT`. Make sure that helper module is included in the repository before running the scraper.

## Features

- Scrapes Rutgers CS professor pages from Rate My Professors.
- Extracts professor-level fields such as quality, difficulty, number of ratings, department, and would-take-again percentage.
- Extracts review-level fields such as review text, quality rating, difficulty rating, grade received, and timestamp.
- Builds a normalized SQLite schema with students, professors, courses, sections, enrollments, and ratings.
- Generates synthetic student profiles, course sections, enrollments, final grades, and ratings.
- Uses real RMP review distributions when possible to make synthetic ratings more realistic.
- Trains a mean-centered `TruncatedSVD` recommendation model.
- Produces top-N professor recommendations for a selected student.
- Generates nine report-ready figures for analysis and evaluation.

## Database Schema

The pipeline recreates the following SQLite tables:

### `student`

Stores synthetic student profile information.

| Column | Description |
|---|---|
| `student_id` | Primary key |
| `student_name_hash` | Anonymous student identifier |
| `preferred_difficulty` | Synthetic difficulty preference from 1 to 5 |
| `interest_level` | Synthetic subject-interest score from 1 to 5 |

### `professor`

Stores professor records.

| Column | Description |
|---|---|
| `professor_id` | Primary key, based on scraper `section_id` |
| `professor_name` | Rutgers professor name |

### `course`

Stores fixed Rutgers CS courses used by the project.

| Column | Description |
|---|---|
| `course_id` | Primary key |
| `course_code` | Rutgers course code, such as `01:198:210` |
| `course_name` | Course title |

### `section`

Connects professors to courses by semester and year.

| Column | Description |
|---|---|
| `section_id` | Primary key |
| `course_id` | Foreign key to `course` |
| `professor_id` | Foreign key to `professor` |
| `semester` | Fall or Spring |
| `year` | Academic year |

### `enrollment`

Connects students to sections.

| Column | Description |
|---|---|
| `enrollment_id` | Primary key |
| `student_id` | Foreign key to `student` |
| `section_id` | Foreign key to `section` |
| `final_grade` | Synthetic final grade |

### `rating`

Stores student ratings and review text.

| Column | Description |
|---|---|
| `rating_id` | Primary key |
| `student_id` | Foreign key to `student` |
| `section_id` | Foreign key to `section` |
| `rating` | Integer rating from 1 to 5 |
| `review_text` | Review text sampled from scraped RMP reviews |

## Requirements

Recommended Python version: **Python 3.10+**

Install the required packages:

```bash
pip install pandas numpy scikit-learn matplotlib seaborn requests beautifulsoup4 selenium webdriver-manager
```

For a reproducible setup, you can also create a `requirements.txt` file:

```text
pandas
numpy
scikit-learn
matplotlib
seaborn
requests
beautifulsoup4
selenium
webdriver-manager
```

## Setup Instructions

### 1. Clone or open the project folder

```bash
cd path/to/profmatch
```

### 2. Create and activate a virtual environment

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install pandas numpy scikit-learn matplotlib seaborn requests beautifulsoup4 selenium webdriver-manager
```

### 4. Make sure Chrome is installed

The scraper uses Selenium with ChromeDriver through `webdriver-manager`, so Google Chrome must be installed on your machine.

## How to Run the Project

### Step 1: Scrape professor and review data

Run the scraper first:

```bash
python seleniumScrapingRating.py
```

This creates:

```text
Data/rutgers_cs_rmp_ratings.csv
Data/rutgers_cs_rmp_reviews.csv
```

The scraper:

1. Gets Rutgers CS professor names.
2. Searches Rate My Professors for each professor.
3. Opens each professor page with Selenium.
4. Clicks “Load More Ratings” until all reviews are visible.
5. Extracts professor-level and review-level data.
6. Saves the output CSV files in the `Data/` folder.

### Step 2: Build the SQLite database and train the recommender

Run the main pipeline:

```bash
python pipeline.py
```

By default, this reads:

```text
Data/rutgers_cs_rmp_ratings.csv
Data/rutgers_cs_rmp_reviews.csv
```

and writes:

```text
profmatch.db
```

It also prints top professor recommendations for a demo student.

### Optional: Run with custom arguments

```bash
python pipeline.py \
  --ratings Data/rutgers_cs_rmp_ratings.csv \
  --reviews Data/rutgers_cs_rmp_reviews.csv \
  --db profmatch.db \
  --students 150 \
  --sections 3 \
  --extra 400 \
  --demo-student 1 \
  --top-n 5
```

### Pipeline Arguments

| Argument | Default | Description |
|---|---:|---|
| `--ratings` | `Data/rutgers_cs_rmp_ratings.csv` | Professor-level CSV from scraper |
| `--reviews` | `Data/rutgers_cs_rmp_reviews.csv` | Review-level CSV from scraper |
| `--db` | `profmatch.db` | SQLite database path |
| `--students` | `150` | Number of synthetic students to generate |
| `--sections` | `3` | Number of synthetic sections per professor |
| `--extra` | `400` | Additional synthetic ratings to generate |
| `--demo-student` | `1` | Student ID used for sample recommendations |
| `--top-n` | `5` | Number of recommendations to print |

### Step 3: Generate visualizations

After `profmatch.db` exists, run:

```bash
python visualizations.py
```

This creates a `figures/` folder and saves the following charts:

| Figure | Output File | Description |
|---|---|---|
| Fig 1 | `fig1_rating_distribution.png` | Distribution of 1–5 star ratings |
| Fig 2 | `fig2_top_professors.png` | Top 10 professors by average rating |
| Fig 3 | `fig3_sparsity_heatmap.png` | Student-professor interaction matrix sparsity |
| Fig 4 | `fig4_ratings_per_student.png` | Number of ratings per student |
| Fig 5 | `fig5_svd_explained_variance.png` | Explained variance by SVD latent factors |
| Fig 6 | `fig6_latent_scatter.png` | Student latent-factor embedding |
| Fig 7 | `fig7_grade_distribution.png` | Final grade distribution |
| Fig 8 | `fig8_rating_vs_grade.png` | Professor rating vs. final grade |
| Fig 9 | `fig9_rmse_vs_k.png` | SVD RMSE across k values |

## Recommendation Model

The recommender is implemented in `ProfessorRecommender` inside `pipeline.py`.

### Model Approach

1. Query all student-professor ratings from SQLite.
2. Build a student × professor interaction matrix.
3. Mean-center each student’s ratings to reduce individual rating bias.
4. Fill missing centered values with `0`.
5. Fit `sklearn.decomposition.TruncatedSVD`.
6. Reconstruct predicted ratings.
7. Add student means back to un-center the predictions.
8. Clip predictions to the 1–5 rating scale.
9. Recommend the highest predicted unrated professors.

### Example Output

```text
Top-5 recommendations for student 1:
 professor_id professor_name  predicted_rating
          12   Example Name              4.82
          28   Example Name              4.71
          35   Example Name              4.63
```

## Data Notes

- Professor and review data come from Rate My Professors pages found through the scraper.
- Student profiles, sections, enrollments, final grades, and some ratings are synthetically generated.
- For professors with more than 50 RMP reviews, the pipeline samples from real scraped `quality_rating` values when generating synthetic ratings.
- For professors with fewer reviews, the pipeline samples from a normal distribution centered on the professor’s average RMP quality score.
- The project uses synthetic student names/hashes instead of real student identities.

## Limitations

- The recommender depends on synthetic student behavior, so the results should be interpreted as a prototype rather than a production-ready advising tool.
- Rate My Professors data is self-reported and may contain bias.
- Web scraping can break if Rate My Professors changes its page layout.
- The SVD model performs best with denser rating matrices; sparse synthetic data limits recommendation accuracy.
- The current pipeline overwrites/recreates the database tables each time `pipeline.py` runs.

## Troubleshooting

### `ModuleNotFoundError: No module named 'utils'`

`seleniumScrapingRating.py` depends on a local helper module:

```python
from utils.utils import clean_text, get_rutgers_cs_professors, DEFAULT_HEADERS, DEFAULT_TIMEOUT
```

Make sure the repository includes:

```text
utils/
└── utils.py
```

### `FileNotFoundError: Ratings CSV not found`

Run the scraper before the pipeline:

```bash
python seleniumScrapingRating.py
python pipeline.py
```

Or pass the correct CSV locations manually:

```bash
python pipeline.py --ratings path/to/ratings.csv --reviews path/to/reviews.csv
```

### Selenium/ChromeDriver errors

Make sure Google Chrome is installed and dependencies are up to date:

```bash
pip install --upgrade selenium webdriver-manager
```

### Empty or weak recommendations

This usually means the database has too few ratings or the selected demo student has no rating history. Try generating more synthetic data:

```bash
python pipeline.py --students 200 --sections 4 --extra 1000 --demo-student 1
```


## Future Improvements

- Add a front-end interface where students can input preferences.
- Add course-specific recommendations instead of general professor recommendations.
- Include more real enrollment/rating data if available.
- Improve professor matching between Rutgers names and RMP pages.
- Add evaluation metrics such as precision@k or held-out rating prediction accuracy.
- Store scraper run timestamps and data provenance metadata.
- Package the project with a complete `requirements.txt` and automated setup script.

