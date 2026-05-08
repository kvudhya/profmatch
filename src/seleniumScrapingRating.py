import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path

# --- SELENIUM IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

from utils.utils import clean_text, get_rutgers_cs_professors, DEFAULT_HEADERS, DEFAULT_TIMEOUT

PROFESSOR_OUTPUT_FILE = "rutgers_cs_rmp_ratings.csv"
REVIEWS_OUTPUT_FILE = "rutgers_cs_rmp_reviews.csv"

RMP_SCHOOL_ID = 825  # found this by searching the HTML code


#Selenium code(Start up)
def init_webdriver():
    options = Options()
    options.add_argument("--headless")  # Runs in background (Required for smooth WSL execution)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Initialize the Chrome driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver


#different from utils.py
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


def search_rmp_professor(professor_name):
    search_url = f"https://www.ratemyprofessors.com/search/professors/{RMP_SCHOOL_ID}"
    params = {"q": professor_name}

    response = requests.get(search_url, headers=DEFAULT_HEADERS, params=params, timeout=DEFAULT_TIMEOUT)
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



def scrape_rmp_professor_page(driver, professor_url):
    driver.get(professor_url)

    # Handle the cookie consent popup if it appears (it blocks clicks)
    try:
        cookie_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Close')]"))
        )
        cookie_btn.click()
    except TimeoutException:
        pass  # No cookie popup

    # Continuously click "Load More Ratings" until it's gone
    click_count = 0
    while True:
        try:
            load_more_btn = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.XPATH, "//button[text()='Load More Ratings']"))
            )
            # Scroll to button and click via JavaScript to avoid interception errors
            driver.execute_script("arguments[0].scrollIntoView();", load_more_btn)
            driver.execute_script("arguments[0].click();", load_more_btn)
            click_count += 1
            time.sleep(0.5)  # Give the DOM a moment to render the new reviews
        except TimeoutException:
            # Button is no longer found, we've loaded everything
            break
        except Exception as e:
            print(f"      [!] Stopped expanding reviews after {click_count} clicks.")
            break

    # Hand the fully expanded HTML over to BeautifulSoup
    soup = BeautifulSoup(driver.page_source, "html.parser")
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
        r"Quality\s*(\d+(?:\.\d+)?)",
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



def scrape_reviews_from_page(soup, page_text, section_id):
    review_rows = []
    review_counter = 1

    reviews = re.findall(
        r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s+\d{4})?)(.*?)\sHelpful",
        page_text,
        flags=re.IGNORECASE
    )

    for review in reviews:
        block_text = clean_text(review[2])

        quality_rating = None
        quality_match = re.search(r"Quality\s(\d+(?:\.\d+)?)\s", block_text, flags=re.IGNORECASE)
        if quality_match:
            quality_rating = safe_float(quality_match.group(1))

        difficulty_rating = None
        difficulty_match = re.search(r"Difficulty\s(\d+(?:\.\d+)?)\s", block_text, flags=re.IGNORECASE)
        if difficulty_match:
            difficulty_rating = safe_float(difficulty_match.group(1))

        # helpfulness_rating = None
        # helpful_match = re.search(r"Helpful\s*[:\-]?\s*(\d+(?:\.\d+)?)", block_text, flags=re.IGNORECASE)
        # if helpful_match:
        #     helpfulness_rating = safe_float(helpful_match.group(1))

        grade_received = None
        grade_match = re.search(r"Grade\s:\s([A-D][+-]?|[EF])", block_text, flags=re.IGNORECASE)
        if grade_match:
            grade_received = clean_text(grade_match.group(1))

        timestamp = None
        time_match = re.search(
            r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s+\d{4})?)",
            block_text,
            flags=re.IGNORECASE
        )
        if time_match:
            timestamp = clean_text(time_match.group(1))

        review_text = None
        pattern = re.compile(
            r'.*(?:Textbook|Grade|Would Take Again|Attendance|For Credit)\s*:\s*(?:[A-Za-z/+-]+(?:\s+[A-Za-z/+-]+)?)\s+(.*)',
            re.IGNORECASE | re.DOTALL
        )

        match = pattern.search(block_text)
        if match:
            review_text = clean_text(match.group(1))

        review_rows.append(
            {
                "review_id": review_counter,
                "section_id": section_id,
                "quality_rating": quality_rating,
                "review_text": review_text,
                "difficulty_rating": difficulty_rating,
                "grade_received": grade_received,
                "timestamp": timestamp
            }
        )
        review_counter += 1

    return review_rows



def build_rutgers_cs_rmp_dataset():
    BASE_DIR = Path("Data")
    BASE_DIR.mkdir(exist_ok=True)  # Ensures the Data folder exists
    modify_prof_file = BASE_DIR / PROFESSOR_OUTPUT_FILE
    modify_review_file = BASE_DIR / REVIEWS_OUTPUT_FILE

    professor_names = get_rutgers_cs_professors()
    print(f"Found {len(professor_names)} Rutgers CS professors")

    professor_rows = []
    all_review_rows = []

    # Initialize the browser once
    print("Initializing Selenium WebDriver...")
    driver = init_webdriver()

    try:
        for i, professor_name in enumerate(professor_names, start=1):
            print(f"[{i}/{len(professor_names)}] Searching RMP for: {professor_name}")

            row = {
                "section_id": i,
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
                # We still use normal requests to quickly grab the search URL
                rmp_url = search_rmp_professor(professor_name)

                if rmp_url:
                    # Pass the driver to the modified scrape function
                    rmp_data, soup, page_text = scrape_rmp_professor_page(driver, rmp_url)
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

    finally:
        # Guarantee the browser closes even if the script crashes
        driver.quit()
        print("WebDriver closed.")

    professors_df = pd.DataFrame(professor_rows)
    reviews_df = pd.DataFrame(all_review_rows)

    professors_df.to_csv(modify_prof_file, index=False)
    reviews_df.to_csv(modify_review_file, index=False)

    print(f"\nSaved professor file to: {modify_prof_file}")
    print(f"Saved review file to: {modify_review_file}")

    return professors_df, reviews_df


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    professors_df, reviews_df = build_rutgers_cs_rmp_dataset()

    print("\nProfessor DataFrame:")
    print(professors_df.head(10))

    print("\nReviews DataFrame:")
    print(reviews_df.head(10))