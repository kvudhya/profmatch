

import os
import re
import unittest
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler


# %% [markdown]
# ## 1. Configuration

# %%
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

DEFAULT_TIMEOUT = 15
OUTPUT_FILE = "recommended_professors_output.csv"

# Add direct public professor page URLs here if you have them.
RMP_PROFESSOR_PAGES = [
    # "https://www.ratemyprofessors.com/professor/1234567",
]

# Public Rutgers course pages
COURSE_MATERIAL_URLS = [
    "https://www.cs.rutgers.edu/academics/undergraduate/course-synopses/course-details/01-198-112-data-structures",
    "https://www.cs.rutgers.edu/academics/undergraduate/course-synopses/course-details/01-198-344-design-and-analysis-of-computer-algorithms",
]


# %% [markdown]
# ## 2. Small utilities

# %%
def clean_text(text):
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_float(value, default=0.0):
    if value is None:
        return default
    text = clean_text(value)
    if not text:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return default
    try:
        return float(match.group())
    except ValueError:
        return default


def safe_percentage(value, default=0.0):
    if value is None:
        return default
    text = clean_text(value).replace("%", "")
    return safe_float(text, default=default)

# %%
professor_rows = []
review_rows = []

for idx, url in enumerate(RMP_PROFESSOR_PAGES, start=1):
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        html = response.text

        soup = BeautifulSoup(html, "html.parser")
        page_text = clean_text(soup.get_text(" ", strip=True))

        name = "Unknown Professor"
        department = "Unknown Department"
        rating = 0.0
        difficulty = 0.0
        would_take_again_pct = 0.0

        title_tag = soup.find("title")
        if title_tag and clean_text(title_tag.text):
            name = clean_text(title_tag.text).split("|")[0].strip()

        possible_name = soup.find(["h1", "h2"])
        if possible_name and clean_text(possible_name.text):
            name = clean_text(possible_name.text)

        department_match = re.search(
            r"(?:Department|Subject|Teaches in Department)[:\s]+([A-Za-z& ,\-]+)",
            page_text,
            flags=re.IGNORECASE,
        )
        if department_match:
            department = clean_text(department_match.group(1))

        rating_match = re.search(
            r"(?:Overall\s+Quality|Rating)[:\s]+(\d(?:\.\d+)?)",
            page_text,
            re.IGNORECASE,
        )
        difficulty_match = re.search(
            r"(?:Level\s+of\s+Difficulty|Difficulty)[:\s]+(\d(?:\.\d+)?)",
            page_text,
            re.IGNORECASE,
        )
        take_again_match = re.search(
            r"(?:Would\s+Take\s+Again)[:\s]+(\d{1,3})%",
            page_text,
            re.IGNORECASE,
        )

        if rating_match:
            rating = safe_float(rating_match.group(1))
        if difficulty_match:
            difficulty = safe_float(difficulty_match.group(1))
        if take_again_match:
            would_take_again_pct = safe_percentage(take_again_match.group(1))

        review_sentences = []
        for paragraph in soup.find_all(["p", "div", "span"]):
            text = clean_text(paragraph.get_text(" ", strip=True))
            if text and 20 <= len(text) <= 300:
                review_sentences.append(text)

        review_text = " ".join(review_sentences[:10])
        if not review_text:
            review_text = page_text[:1000]

        professor_rows.append(
            {
                "prof_id": idx,
                "name": name,
                "department": department,
                "rmp_rating": rating,
                "rmp_difficulty": difficulty,
                "would_take_again_pct": would_take_again_pct,
            }
        )

        review_rows.append(
            {
                "prof_id": idx,
                "review_text": review_text,
            }
        )

    except requests.RequestException as exc:
        print(f"Failed to fetch {url}: {exc}")

scraped_professors_df = pd.DataFrame(professor_rows)
scraped_reviews_df = pd.DataFrame(review_rows)

print(f"Scraped professor rows: {len(scraped_professors_df)}")

