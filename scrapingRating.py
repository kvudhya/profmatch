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
# 3. Pull rating, difficulty, would take again, #ratings
# 4. Save everything to CSV
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 15
OUTPUT_FILE = "rutgers_cs_rmp_ratings.csv"

# Rutgers NB / State University of New Jersey search page on RMP
# This school id is based on the public Rutgers RMP search page.
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
    """
    Scrapes professor names from Rutgers CS professors page.
    """
    response = requests.get(RUTGERS_CS_PROFESSORS_URL, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    professor_names = set()

    # Rutgers page usually has professor names inside headings
    for tag in soup.find_all(["h2", "h3", "h4"]):
        name = clean_text(tag.get_text(" ", strip=True))

        # basic filtering so we don't accidentally grab random headings
        if len(name.split()) >= 2 and len(name) < 60:
            if not any(word in name.lower() for word in ["information", "professors", "close"]):
                professor_names.add(name)

    # sort for cleaner output
    professor_names = sorted(professor_names)

    return professor_names


# -------------------------
# step 2: search professor on RMP
# -------------------------
def search_rmp_professor(professor_name):
    """
    Searches for a professor in Rutgers RMP search results.
    Returns best matching professor page URL if found.
    """

    search_url = f"https://www.ratemyprofessors.com/search/professors/{RMP_SCHOOL_ID}"
    params = {"q": professor_name}

    response = requests.get(search_url, headers=HEADERS, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # first try actual links
    professor_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = clean_text(a.get_text(" ", strip=True))

        if "/professor/" in href:
            full_url = href if href.startswith("http") else "https://www.ratemyprofessors.com" + href
            professor_links.append((text, full_url))

    # try to find the best text match
    target = normalize_name(professor_name)

    for text, url in professor_links:
        if target in normalize_name(text) or normalize_name(text) in target:
            return url

    # fallback:
    # sometimes the search page text contains the professor name even if
    # structure is weird, so try regex on raw html for /professor/ links
    html = response.text
    id_matches = re.findall(r'\/professor\/(\d+)', html)

    if id_matches:
        # just return the first hit if there is at least something
        return f"https://www.ratemyprofessors.com/professor/{id_matches[0]}"

    return None


# -------------------------
# step 3: scrape professor page
# -------------------------
def scrape_rmp_professor_page(professor_url):
    """
    Scrapes one Rate My Professors professor page.
    """
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

    # professor name
    h1 = soup.find("h1")
    if h1:
        data["rmp_name"] = clean_text(h1.get_text(" ", strip=True))

    # department
    dept_match = re.search(
        r"Professor in the (.+?) department at Rutgers",
        page_text,
        flags=re.IGNORECASE
    )
    if dept_match:
        data["department"] = clean_text(dept_match.group(1))

    # would take again
    take_again_match = re.search(
        r"(\d+)%\s*Would take again",
        page_text,
        flags=re.IGNORECASE
    )
    if take_again_match:
        data["would_take_again_pct"] = safe_float(take_again_match.group(1))

    # difficulty
    difficulty_match = re.search(
        r"(\d+(?:\.\d+)?)\s*Level of Difficulty",
        page_text,
        flags=re.IGNORECASE
    )
    if difficulty_match:
        data["difficulty"] = safe_float(difficulty_match.group(1))

    # quality and rating count often show up together on search pages / page text
    # try multiple patterns because RMP HTML can be annoying
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

    return data


# -------------------------
# main pipeline
# -------------------------
def build_rutgers_cs_rmp_dataset():
    professor_names = get_rutgers_cs_professors()
    print(f"Found {len(professor_names)} Rutgers CS professors")

    rows = []

    for i, professor_name in enumerate(professor_names, start=1):
        print(f"[{i}/{len(professor_names)}] Searching RMP for: {professor_name}")

        row = {
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
                rmp_data = scrape_rmp_professor_page(rmp_url)
                row.update(rmp_data)
                row["found_on_rmp"] = True
            else:
                print(f"   No RMP page found for {professor_name}")

        except Exception as e:
            print(f"   Error with {professor_name}: {e}")

        rows.append(row)

        # be a little nicer to the site
        time.sleep(1)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved file to: {OUTPUT_FILE}")

    return df


# -------------------------
# run
# -------------------------
if __name__ == "__main__":
    df = build_rutgers_cs_rmp_dataset()
    print(df.head(10))