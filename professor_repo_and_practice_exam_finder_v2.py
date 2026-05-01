#!/usr/bin/env python3
"""
professor_repo_and_practice_exam_finder_v2.py

Changes from v1:
- You can now use either:
  1) --professors_csv path/to/file.csv
  2) --professor_names "Name One,Name Two,Name Three"

This avoids requiring a CSV if you already know the professor names.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 20

PRACTICE_EXAM_PATTERNS = [
    r"practice[\s_\-]*exam",
    r"sample[\s_\-]*exam",
    r"old[\s_\-]*exam",
    r"previous[\s_\-]*exam",
    r"exam[\s_\-]*prep",
    r"review[\s_\-]*(sheet|guide|packet)",
    r"midterm[\s_\-]*(review|practice|prep)?",
    r"final[\s_\-]*(review|practice|prep)?",
    r"mock[\s_\-]*exam",
    r"quiz[\s_\-]*review",
]

REPO_KEYWORDS = [
    "course", "class", "teaching", "lecture", "assignment", "homework",
    "syllabus", "midterm", "final", "exam", "practice", "review", "rutgers",
]

TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".tex", ".pdf", ".docx", ".pptx",
    ".ipynb", ".html", ".htm", ".csv", ".json", ".yaml", ".yml"
}


@dataclass
class Professor:
    professor_name: str
    github_username: str = ""
    rutgers_page: str = ""
    course_code: str = ""
    course_title: str = ""


@dataclass
class RepoMatch:
    professor_name: str
    github_username: str
    course_query: str
    repository_full_name: str
    repository_name: str
    html_url: str
    description: str
    owner_login: str
    stargazers_count: int
    updated_at: str
    language: str
    match_reason: str
    relevance_score: float


@dataclass
class PracticeExamHit:
    professor_name: str
    repository_full_name: str
    repository_url: str
    path: str
    item_type: str
    item_url: str
    matched_pattern: str
    confidence: str


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize(text: str) -> str:
    text = clean_text(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


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


class GitHubClient:
    def __init__(self, token: Optional[str] = None, sleep_seconds: float = 0.5) -> None:
        self.session = requests.Session()
        self.sleep_seconds = sleep_seconds
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "profmatch-public-github-research-script",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        resp = self.session.get(url, headers=self.headers, params=params, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise RuntimeError("GitHub rate limit hit. Use --github_token or wait and retry.")
        resp.raise_for_status()
        time.sleep(self.sleep_seconds)
        return resp

    def search_repositories(self, query: str, per_page: int = 10) -> List[Dict[str, Any]]:
        url = f"{GITHUB_API}/search/repositories"
        params = {"q": query, "per_page": per_page, "sort": "updated", "order": "desc"}
        return self.get(url, params=params).json().get("items", [])

    def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}".rstrip("/")
        data = self.get(url).json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    def get_file_text_if_small(self, owner: str, repo: str, path: str, max_bytes: int = 200_000) -> str:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        data = self.get(url).json()
        size = int(data.get("size", 0))
        if size > max_bytes:
            return ""
        if data.get("encoding") == "base64" and data.get("content"):
            raw = base64.b64decode(data["content"])
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return ""


def build_repo_queries(prof: Professor, course_query: str) -> List[Tuple[str, str]]:
    queries: List[Tuple[str, str]] = []
    name = prof.professor_name
    course_bits = [course_query]
    if prof.course_code and prof.course_code.lower() not in course_query.lower():
        course_bits.append(prof.course_code)
    if prof.course_title and prof.course_title.lower() not in course_query.lower():
        course_bits.append(prof.course_title)
    course_blob = " ".join(bit for bit in course_bits if bit).strip()

    if prof.github_username:
        queries.append((f'user:{prof.github_username} "{course_blob}" (rutgers OR course OR class OR teaching)', "known_username_course_query"))
        queries.append((f'user:{prof.github_username} (midterm OR final OR exam OR practice OR review OR syllabus)', "known_username_exam_material_query"))

    queries.append((f'"{name}" "{course_blob}" (rutgers OR course OR class OR teaching)', "name_plus_course_query"))
    queries.append((f'"{name}" rutgers (midterm OR final OR exam OR practice OR review)', "name_plus_exam_terms_query"))
    return queries


def repo_relevance_score(repo: Dict[str, Any], prof: Professor, course_query: str) -> Tuple[float, str]:
    haystack = " ".join([
        clean_text(repo.get("name")),
        clean_text(repo.get("full_name")),
        clean_text(repo.get("description")),
        clean_text(repo.get("homepage")),
        clean_text(repo.get("owner", {}).get("login")),
    ]).lower()

    score = 0.0
    reasons: List[str] = []

    prof_name_norm = normalize(prof.professor_name)
    owner_norm = normalize(clean_text(repo.get("owner", {}).get("login")))
    repo_name_norm = normalize(clean_text(repo.get("name")))
    course_norm = normalize(course_query)
    last_name = prof_name_norm.split()[-1] if prof_name_norm else ""

    if prof.github_username and repo.get("owner", {}).get("login", "").lower() == prof.github_username.lower():
        score += 4.0
        reasons.append("owner matches provided github_username")

    if last_name and (last_name in owner_norm or last_name in repo_name_norm or last_name in haystack):
        score += 1.5
        reasons.append("professor last name appears")

    for token in course_norm.split():
        if token and token in haystack:
            score += 0.6

    for kw in REPO_KEYWORDS:
        if kw in haystack:
            score += 0.2

    if "rutgers" in haystack:
        score += 0.7
        reasons.append("mentions rutgers")

    desc = clean_text(repo.get("description")).lower()
    if any(term in desc for term in ["teaching", "course", "class", "lecture", "assignment", "syllabus"]):
        score += 0.8
        reasons.append("teaching/course-like description")

    return score, "; ".join(reasons) if reasons else "weak heuristic match"


def looks_like_practice_exam(path: str, file_type: str, text_preview: str = "") -> Optional[str]:
    target = f"{path} {text_preview}".lower()
    for pattern in PRACTICE_EXAM_PATTERNS:
        if re.search(pattern, target, flags=re.IGNORECASE):
            return pattern
    if file_type == "dir" and any(k in target for k in ["exam", "review", "practice", "midterm", "final"]):
        return "directory_exam_keyword"
    return None


def should_descend_dir(dirname: str) -> bool:
    d = dirname.lower()
    return any(k in d for k in [
        "exam", "review", "practice", "midterm", "final", "quiz",
        "course", "class", "teaching", "lecture", "materials", "resources"
    ])


def inspect_repo_for_exam_materials(gh: GitHubClient, repo: Dict[str, Any], professor_name: str, max_depth: int = 2) -> List[PracticeExamHit]:
    owner = repo["owner"]["login"]
    repo_name = repo["name"]
    html_url = repo["html_url"]
    hits: List[PracticeExamHit] = []

    def walk(path: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            items = gh.get_repo_contents(owner, repo_name, path)
        except Exception:
            return

        for item in items:
            item_path = item.get("path", "")
            item_type = item.get("type", "")
            item_url = item.get("html_url", "")
            text_preview = ""
            _, ext = os.path.splitext(item_path.lower())

            if item_type == "file" and ext in TEXT_EXTENSIONS:
                filename = os.path.basename(item_path).lower()
                if any(token in filename for token in ["exam", "review", "practice", "midterm", "final", "quiz"]):
                    try:
                        text_preview = gh.get_file_text_if_small(owner, repo_name, item_path)[:4000]
                    except Exception:
                        text_preview = ""

            matched = looks_like_practice_exam(item_path, item_type, text_preview)
            if matched:
                confidence = "high" if item_type == "file" else "medium"
                hits.append(
                    PracticeExamHit(
                        professor_name=professor_name,
                        repository_full_name=repo["full_name"],
                        repository_url=html_url,
                        path=item_path,
                        item_type=item_type,
                        item_url=item_url,
                        matched_pattern=matched,
                        confidence=confidence,
                    )
                )

            if item_type == "dir" and should_descend_dir(item_path):
                walk(item_path, depth + 1)

    walk("", 0)
    return hits


def unique_repos(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []
    for repo in items:
        full_name = repo.get("full_name")
        if full_name and full_name not in seen:
            seen.add(full_name)
            unique.append(repo)
    return unique


def ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", required=True)
    parser.add_argument("--professors_csv", default="")
    parser.add_argument("--professor_names", default="")
    parser.add_argument("--output_dir", default="github_course_repo_results")
    parser.add_argument("--github_token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--per_query_limit", type=int, default=8)
    parser.add_argument("--repo_score_threshold", type=float, default=1.6)
    parser.add_argument("--max_repo_scan", type=int, default=10)
    args = parser.parse_args()

    if not args.professors_csv and not args.professor_names:
        raise ValueError("Provide either --professors_csv or --professor_names.")

    if args.professors_csv:
        professors = load_professors(args.professors_csv)
    else:
        professors = parse_professor_names(args.professor_names, course_query=args.course)

    if not professors:
        raise ValueError("No professors loaded.")

    ensure_output_dir(args.output_dir)
    gh = GitHubClient(token=args.github_token or None)

    repo_matches: List[RepoMatch] = []
    practice_hits: List[PracticeExamHit] = []

    for prof in professors:
        all_candidate_repos: List[Dict[str, Any]] = []

        for query, _ in build_repo_queries(prof, args.course):
            try:
                repos = gh.search_repositories(query=query, per_page=args.per_query_limit)
            except Exception as exc:
                print(f"[WARN] search failed for {prof.professor_name}: {exc}", file=sys.stderr)
                continue
            all_candidate_repos.extend(repos)

        deduped = unique_repos(all_candidate_repos)
        scored: List[Tuple[float, str, Dict[str, Any]]] = []

        for repo in deduped:
            score, reason = repo_relevance_score(repo, prof, args.course)
            if score >= args.repo_score_threshold:
                scored.append((score, reason, repo))

        scored.sort(key=lambda x: (x[0], x[2].get("stargazers_count", 0)), reverse=True)
        kept = scored[: args.max_repo_scan]

        for score, reason, repo in kept:
            repo_matches.append(
                RepoMatch(
                    professor_name=prof.professor_name,
                    github_username=prof.github_username,
                    course_query=args.course,
                    repository_full_name=repo.get("full_name", ""),
                    repository_name=repo.get("name", ""),
                    html_url=repo.get("html_url", ""),
                    description=clean_text(repo.get("description")),
                    owner_login=repo.get("owner", {}).get("login", ""),
                    stargazers_count=int(repo.get("stargazers_count", 0)),
                    updated_at=clean_text(repo.get("updated_at")),
                    language=clean_text(repo.get("language")),
                    match_reason=reason,
                    relevance_score=round(score, 3),
                )
            )

            try:
                hits = inspect_repo_for_exam_materials(gh, repo, prof.professor_name)
                practice_hits.extend(hits)
            except Exception as exc:
                print(f"[WARN] scan failed for {repo.get('full_name')}: {exc}", file=sys.stderr)

    repo_rows = [asdict(x) for x in repo_matches]
    hit_rows = [asdict(x) for x in practice_hits]

    save_csv(os.path.join(args.output_dir, "repos_found.csv"), repo_rows)
    save_csv(os.path.join(args.output_dir, "practice_exam_hits.csv"), hit_rows)

    with open(os.path.join(args.output_dir, "repos_found.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "course_query": args.course,
                "professor_count": len(professors),
                "repo_count": len(repo_rows),
                "practice_exam_hit_count": len(hit_rows),
                "repos": repo_rows,
                "practice_exam_hits": hit_rows,
            },
            f,
            indent=2,
        )

    print(f"Saved {len(repo_rows)} repository matches.")
    print(f"Saved {len(hit_rows)} practice-exam-style hits.")
    print(f"Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
