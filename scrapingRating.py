import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

# =========================================================
# scrapingRating.py
# Goal:
# 1. Scrape Rutgers CS professor names from Rutgers CS site
# 2. Search each professor on Rate My Professors
# 3. Pull professor-level data
# 4. Pull review-level data
# 5. Save both to CSV
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 15
PROFESSOR_OUTPUT_FILE = "rutgers_cs_rmp_ratings.csv"
REVIEWS_OUTPUT_FILE = "rutgers_cs_rmp_reviews.csv"

RMP_SCHOOL_ID = 825
RUTGERS_CS_PROFESSORS_URL = "https://www.cs.rutgers.edu/people/professors"


# -------------------------
# small helper functions
# -------------------------
def clean_text(text):
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def safe_float(text, default=None):
    if text is None:
        return default
    match = re.search(r"\d+(?:\.\d+)?", str(text))
    if match:
        try:
            return float(match.group())
        except:
            return default
    return default


def safe_int(text, default=None):
    if text is None:
        return default
    match = re.search(r"\d+", str(text).replace(",", ""))
    if match:
        try:
            return int(match.group())
        except:
            return default
    return default


def normalize_name(name):
    name = clean_text(name).lower()
    name = re.sub(r"[^a-z\s\-']", "", name)
    return name


# -------------------------
# step 1: get Rutgers CS professors
# -------------------------
def get_rutgers_cs_professors():
    response = requests.get(RUTGERS_CS_PROFESSORS_URL, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    professor_names = set()

    for tag in soup.find_all(["h2", "h3", "h4"]):
        name = clean_text(tag.get_text(" ", strip=True))

        if len(name.split()) >= 2 and len(name) < 60:
            if not any(word in name.lower() for word in ["information", "professors", "close"]):
                professor_names.add(name)

    return sorted(professor_names)


# -------------------------
# step 2: search professor on RMP
# -------------------------
def search_rmp_professor(professor_name):
    search_url = f"https://www.ratemyprofessors.com/search/professors/{RMP_SCHOOL_ID}"
    params = {"q": professor_name}

    response = requests.get(search_url, headers=HEADERS, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    professor_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = clean_text(a.get_text(" ", strip=True))

        if "/professor/" in href:
            full_url = href if href.startswith("http") else "https://www.ratemyprofessors.com" + href
            professor_links.append((text, full_url))

    target = normalize_name(professor_name)

    for text, url in professor_links:
        if target in normalize_name(text) or normalize_name(text) in target:
            return url

    html = response.text
    id_matches = re.findall(r'\/professor\/(\d+)', html)
    if id_matches:
        return f"https://www.ratemyprofessors.com/professor/{id_matches[0]}"

    return None


# -------------------------
# step 3: scrape professor page
# -------------------------
def scrape_rmp_professor_page(professor_url):
    response = requests.get(professor_url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = clean_text(soup.get_text(" ", strip=True))

    data = {
        "rmp_name": None,
        "department": None,
        "quality": None,
        "difficulty": None,
        "would_take_again_pct": None,
        "num_ratings": None,
        "rmp_url": professor_url
    }

    h1 = soup.find("h1")
    if h1:
        data["rmp_name"] = clean_text(h1.get_text(" ", strip=True))

    dept_match = re.search(
        r"Professor in the (.+?) department at Rutgers",
        page_text,
        flags=re.IGNORECASE
    )
    if dept_match:
        data["department"] = clean_text(dept_match.group(1))

    take_again_match = re.search(
        r"(\d+)%\s*Would take again",
        page_text,
        flags=re.IGNORECASE
    )
    if take_again_match:
        data["would_take_again_pct"] = safe_float(take_again_match.group(1))

    difficulty_match = re.search(
        r"(\d+(?:\.\d+)?)\s*Level of Difficulty",
        page_text,
        flags=re.IGNORECASE
    )
    if difficulty_match:
        data["difficulty"] = safe_float(difficulty_match.group(1))

    quality_match = re.search(
        r"Quality\s*(\d(?:\.\d+)?)",
        page_text,
        flags=re.IGNORECASE
    )
    if quality_match:
        data["quality"] = safe_float(quality_match.group(1))

    ratings_match = re.search(
        r"(\d+)\s*ratings?",
        page_text,
        flags=re.IGNORECASE
    )
    if ratings_match:
        data["num_ratings"] = safe_int(ratings_match.group(1))

    return data, soup, page_text


# -------------------------
# step 4: scrape review-level data
# reviews(review_id PK, section_id FK, review_text,
#         helpfulness_rating, difficulty_rating,
#         grade_received, timestamp)
# -------------------------
def scrape_reviews_from_page(soup, page_text, section_id):
    review_rows = []

    # Try to find review blocks
    possible_review_blocks = soup.find_all(["div", "li", "article"])

    review_counter = 1

    for block in possible_review_blocks:
        block_text = clean_text(block.get_text(" ", strip=True))

        # basic filter so we don't collect random junk
        if len(block_text) < 40:
            continue

        # review text
        review_text = None
        if 40 <= len(block_text) <= 1500:
            review_text = block_text

        if not review_text:
            continue

        # difficulty inside each review block if present
        difficulty_rating = None
        difficulty_match = re.search(
            r"Difficulty\s*[:\-]?\s*(\d(?:\.\d+)?)",
            block_text,
            flags=re.IGNORECASE
        )
        if difficulty_match:
            difficulty_rating = safe_float(difficulty_match.group(1))

        # helpfulness rating may not actually exist on RMP pages anymore
        helpfulness_rating = None
        helpful_match = re.search(
            r"Helpful\s*[:\-]?\s*(\d+(?:\.\d+)?)",
            block_text,
            flags=re.IGNORECASE
        )
        if helpful_match:
            helpfulness_rating = safe_float(helpful_match.group(1))

        # grade received if present
        grade_received = None
        grade_match = re.search(
            r"Grade\s*[:\-]?\s*([A-F][+-]?)",
            block_text,
            flags=re.IGNORECASE
        )
        if grade_match:
            grade_received = clean_text(grade_match.group(1))

        # timestamp if present
        timestamp = None
        time_match = re.search(
            r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s+\d{4})?)",
            block_text,
            flags=re.IGNORECASE
        )
        if time_match:
            timestamp = clean_text(time_match.group(1))

        review_rows.append(
            {
                "review_id": review_counter,
                "section_id": section_id,
                "review_text": review_text,
                "helpfulness_rating": helpfulness_rating,
                "difficulty_rating": difficulty_rating,
                "grade_received": grade_received,
                "timestamp": timestamp
            }
        )
        review_counter += 1

    return review_rows


# -------------------------
# main pipeline
# -------------------------
def build_rutgers_cs_rmp_dataset():
    professor_names = get_rutgers_cs_professors()
    print(f"Found {len(professor_names)} Rutgers CS professors")

    professor_rows = []
    all_review_rows = []

    for i, professor_name in enumerate(professor_names, start=1):
        print(f"[{i}/{len(professor_names)}] Searching RMP for: {professor_name}")

        row = {
            "section_id": i,   # using this like your FK target
            "rutgers_name": professor_name,
            "rmp_name": None,
            "department": None,
            "quality": None,
            "difficulty": None,
            "would_take_again_pct": None,
            "num_ratings": None,
            "rmp_url": None,
            "found_on_rmp": False
        }

        try:
            rmp_url = search_rmp_professor(professor_name)

            if rmp_url:
                rmp_data, soup, page_text = scrape_rmp_professor_page(rmp_url)
                row.update(rmp_data)
                row["found_on_rmp"] = True

                review_rows = scrape_reviews_from_page(soup, page_text, i)
                all_review_rows.extend(review_rows)

            else:
                print(f"   No RMP page found for {professor_name}")

        except Exception as e:
            print(f"   Error with {professor_name}: {e}")

        professor_rows.append(row)

        time.sleep(1)

    professors_df = pd.DataFrame(professor_rows)
    reviews_df = pd.DataFrame(all_review_rows)

    professors_df.to_csv(PROFESSOR_OUTPUT_FILE, index=False)
    reviews_df.to_csv(REVIEWS_OUTPUT_FILE, index=False)

    print(f"\nSaved professor file to: {PROFESSOR_OUTPUT_FILE}")
    print(f"Saved review file to: {REVIEWS_OUTPUT_FILE}")

    return professors_df, reviews_df


# -------------------------
# run
# -------------------------
if __name__ == "__main__":
    professors_df, reviews_df = build_rutgers_cs_rmp_dataset()

    print("\nProfessor DataFrame:")
    print(professors_df.head(10))

    print("\nReviews DataFrame:")
    print(reviews_df.head(10))