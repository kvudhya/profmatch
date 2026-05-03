from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re
import csv

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
DEFAULT_TIMEOUT = 20

RUTGERS_CS_FACULTY_URL = "https://www.cs.rutgers.edu/people/directory.php?type=faculty"
RUTGERS_CS_PROFESSORS_URL = "https://www.cs.rutgers.edu/people/professors"


@dataclass
class Professor:
    professor_name: str
    github_username: str = ""
    rutgers_page: str = ""
    course_code: str = ""
    course_title: str = ""


@dataclass
class FacultyMember:
    name: str
    faculty_group: str
    email: Optional[str] = None


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize(text: str) -> str:
    text = clean_text(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def fetch_html(url: str, headers: Optional[Dict] = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    response = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=timeout)
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


def get_rutgers_cs_professors(url: str = RUTGERS_CS_PROFESSORS_URL) -> List[str]:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    professor_names = set()

    for tag in soup.find_all(["h2", "h3", "h4"]):
        name = clean_text(tag.get_text(" ", strip=True))
        if len(name.split()) >= 2 and len(name) < 60:
            if not any(word in name.lower() for word in ["information", "professors", "close"]):
                professor_names.add(name)

    return sorted(professor_names)


def load_professors(csv_path: str) -> List[Professor]:
    professors: List[Professor] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"professor_name"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

        for row in reader:
            name = clean_text(row.get("professor_name"))
            if not name:
                continue
            professors.append(
                Professor(
                    professor_name=name,
                    github_username=clean_text(row.get("github_username")),
                    rutgers_page=clean_text(row.get("rutgers_page")),
                    course_code=clean_text(row.get("course_code")),
                    course_title=clean_text(row.get("course_title")),
                )
            )
    return professors


def parse_professor_names(names_blob: str, course_query: str = "") -> List[Professor]:
    names = [clean_text(x) for x in names_blob.split(",")]
    names = [x for x in names if x]
    return [Professor(professor_name=name, course_code=course_query) for name in names]
