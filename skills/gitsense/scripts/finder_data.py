"""Issue search and candidate fetching pipeline (NO LLM).

Ported from GitSense (https://github.com/he-yufeng/GitSense) — MIT license.
The original rank_with_llm() is deliberately excluded: the Agent uses its
own reasoning to rank candidates instead of an external LLM call.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .github_client import search_issues


def build_search_queries(
    skills: list[str],
    min_stars: int,
    labels: list[str],
    updated_days: int | None = 180,
    include_assigned: bool = False,
) -> list[str]:
    """Build GitHub search queries from user skills and filters."""
    if not skills:
        raise ValueError("skills must not be empty: pass at least one skill")
    queries = []
    filters = ["is:issue", "is:open", "archived:false"]
    if not include_assigned:
        filters.append("no:assignee")
    if min_stars > 0:
        filters.append(f"stars:>={min_stars}")
    if updated_days is not None:
        if updated_days <= 0:
            raise ValueError(f"updated_days must be greater than zero, got {updated_days}")
        since = date.today() - timedelta(days=updated_days)
        filters.append(f"updated:>={since.isoformat()}")
    if labels:
        filters.extend(f'label:"{lab}"' for lab in labels)
    filter_str = " ".join(filters)

    for skill in skills:
        queries.append(f"{skill} {filter_str}")

    # Also search for "good first issue" across skills
    skill_str = " OR ".join(skills[:3])
    queries.append(f'{skill_str} {filter_str} label:"good first issue"')

    return queries


def fetch_candidates(
    skills: list[str],
    min_stars: int = 100,
    labels: list[str] | None = None,
    max_results: int = 30,
    updated_days: int | None = 180,
    max_comments: int | None = None,
    include_assigned: bool = False,
) -> list[dict[str, Any]]:
    """Fetch candidate issues from GitHub. Returns JSON-serializable list."""
    queries = build_search_queries(
        skills,
        min_stars,
        labels or [],
        updated_days=updated_days,
        include_assigned=include_assigned,
    )

    seen_urls = set()
    candidates = []

    for query in queries:
        try:
            issues = search_issues(query, per_page=min(max_results, 20))
        except Exception:
            continue

        for issue in issues:
            url = issue.get("html_url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            comments = issue.get("comments", 0)
            if max_comments is not None and comments > max_comments:
                continue

            repo_url = issue.get("repository_url", "")
            repo_name = "/".join(repo_url.split("/")[-2:]) if repo_url else ""

            candidates.append({
                "title": issue.get("title", ""),
                "url": url,
                "repo": repo_name,
                "labels": [lab["name"] for lab in issue.get("labels", [])],
                "comments": comments,
                "created_at": issue.get("created_at", "")[:10],
                "updated_at": issue.get("updated_at", "")[:10],
                "body": (issue.get("body") or "")[:1000],
            })

    return candidates[:max_results]


def scan_repo_issues(repo: str, skills: list[str] | None = None,
                     updated_days: int = 180,
                     max_comments: int | None = None,
                     max_results: int = 15) -> list[dict[str, Any]]:
    """Scan a specific repo for open unassigned issues."""
    from datetime import date, timedelta
    since = date.today() - timedelta(days=updated_days)
    q = f"repo:{repo} is:issue is:open no:assignee updated:>={since.isoformat()}"
    if skills:
        q += f" {' OR '.join(skills[:3])}"
    issues = search_issues(q, per_page=max_results)
    if max_comments is not None:
        issues = [issue for issue in issues if issue.get("comments", 0) <= max_comments]
    return [
        {
            "number": i.get("number", ""),
            "title": i.get("title", ""),
            "url": i.get("html_url", ""),
            "labels": [lab["name"] for lab in i.get("labels", [])],
            "updated_at": i.get("updated_at", "")[:10],
            "comments": i.get("comments", 0),
            "body": (i.get("body") or "")[:500],
        }
        for i in issues
    ]
