import csv
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import requests

from utils import (
    clean_text,
    fetch_html,
    parse_faculty_directory,
    FacultyMember,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    RUTGERS_CS_FACULTY_URL,
)

MAX_POSTS_PER_PROFESSOR = 10
SLEEP_SECONDS = 1.0


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
    faculty_html = fetch_html(RUTGERS_CS_FACULTY_URL)
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
