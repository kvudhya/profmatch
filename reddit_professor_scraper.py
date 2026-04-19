import csv
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup

FACULTY_URL = "https://www.cs.rutgers.edu/people/directory.php?type=faculty"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
DEFAULT_TIMEOUT = 20
MAX_POSTS_PER_PROFESSOR = 10
SLEEP_SECONDS = 1.0


@dataclass
class FacultyMember:
    name: str
    faculty_group: str
    email: Optional[str] = None


@dataclass
class RedditPostResult:
    professor_name: str
    faculty_group: str
    found: bool
    title: str = ""
    subreddit: str = ""
    post_url: str = ""
    permalink: str = ""
    created_utc: str = ""
    score: Optional[int] = None
    num_comments: Optional[int] = None
    snippet: str = ""
    search_query: str = ""


def clean_text(text: Optional[str]) -> str:
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_faculty_directory(html: str) -> List[FacultyMember]:
    soup = BeautifulSoup(html, "html.parser")
    members: List[FacultyMember] = []

    current_group = None
    for tag in soup.find_all(["h3", "a"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if text in {"Professors", "Teaching Faculty", "Part Time Lecturers"}:
            current_group = text
            continue

        if current_group in {"Professors", "Teaching Faculty"} and tag.name == "a":
            href = tag.get("href", "")
            if not href or href.startswith("#"):
                continue
            if text in {"Image", "Home", "Search"}:
                continue
            if len(text.split()) < 2:
                continue
            if any(token in text for token in ["rutgers.edu", "cs.rutgers.edu"]):
                continue

            members.append(FacultyMember(name=text, faculty_group=current_group))

    deduped = []
    seen = set()
    for member in members:
        key = (member.name.lower(), member.faculty_group)
        if key not in seen:
            deduped.append(member)
            seen.add(key)
    return deduped


def build_search_query(professor_name: str) -> str:
    return f'subreddit:rutgers "{professor_name}" (professor OR class OR cs OR rutgers)'


def utc_to_iso(utc_seconds: Optional[float]) -> str:
    if utc_seconds is None:
        return ""
    try:
        return datetime.fromtimestamp(float(utc_seconds), tz=timezone.utc).isoformat()
    except Exception:
        return ""


def search_reddit_posts(query: str, limit: int = MAX_POSTS_PER_PROFESSOR) -> List[dict]:
    url = "https://www.reddit.com/search.json"
    params = {
        "q": query,
        "limit": limit,
        "sort": "relevance",
        "t": "all",
        "type": "link",
    }
    response = requests.get(url, headers=DEFAULT_HEADERS, params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children]


def normalize_result(professor: FacultyMember, post: dict, query: str) -> RedditPostResult:
    permalink = clean_text(post.get("permalink"))
    if permalink and not permalink.startswith("http"):
        permalink = f"https://www.reddit.com{permalink}"

    return RedditPostResult(
        professor_name=professor.name,
        faculty_group=professor.faculty_group,
        found=True,
        title=clean_text(post.get("title")),
        subreddit=clean_text(post.get("subreddit")),
        post_url=clean_text(post.get("url")),
        permalink=permalink,
        created_utc=utc_to_iso(post.get("created_utc")),
        score=post.get("score"),
        num_comments=post.get("num_comments"),
        snippet=clean_text(post.get("selftext")[:500]),
        search_query=query,
    )


def scrape_all_professor_posts() -> List[RedditPostResult]:
    faculty_html = fetch_html(FACULTY_URL)
    faculty_members = parse_faculty_directory(faculty_html)
    all_rows: List[RedditPostResult] = []

    print(f"Found {len(faculty_members)} Rutgers CS faculty/teaching faculty names.")

    for idx, professor in enumerate(faculty_members, start=1):
        query = build_search_query(professor.name)
        print(f"[{idx}/{len(faculty_members)}] Searching Reddit for {professor.name}...")

        try:
            posts = search_reddit_posts(query=query, limit=MAX_POSTS_PER_PROFESSOR)
        except requests.RequestException as exc:
            print(f"  Failed for {professor.name}: {exc}")
            all_rows.append(
                RedditPostResult(
                    professor_name=professor.name,
                    faculty_group=professor.faculty_group,
                    found=False,
                    search_query=query,
                )
            )
            time.sleep(SLEEP_SECONDS)
            continue

        matched_any = False
        for post in posts:
            title = clean_text(post.get("title"))
            body = clean_text(post.get("selftext"))
            combined = f"{title} {body}".lower()
            if professor.name.lower() not in combined:
                continue
            matched_any = True
            all_rows.append(normalize_result(professor, post, query))

        if not matched_any:
            all_rows.append(
                RedditPostResult(
                    professor_name=professor.name,
                    faculty_group=professor.faculty_group,
                    found=False,
                    search_query=query,
                )
            )

        time.sleep(SLEEP_SECONDS)

    return all_rows


def write_csv(rows: Iterable[RedditPostResult], filepath: str) -> None:
    rows = list(rows)
    if not rows:
        return
    fieldnames = list(asdict(rows[0]).keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(rows: Iterable[RedditPostResult], filepath: str) -> None:
    payload = [asdict(row) for row in rows]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    output_rows = scrape_all_professor_posts()
    write_csv(output_rows, "rutgers_cs_reddit_posts.csv")
    write_json(output_rows, "rutgers_cs_reddit_posts.json")
    print("Saved rutgers_cs_reddit_posts.csv and rutgers_cs_reddit_posts.json")
