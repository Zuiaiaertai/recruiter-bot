"""
Candidate discovery via Google Search (Serper API) and Google Scholar.
"""
import re
import requests
from config import SERPER_API_KEY

SERPER_URL = "https://google.serper.dev/search"


def _search(query: str, num: int = 10) -> list[dict]:
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(SERPER_URL, json={"q": query, "num": num},
                          headers=headers, timeout=12)
        r.raise_for_status()
        return r.json().get("organic", [])
    except Exception as e:
        print(f"  [searcher] Serper error: {e}")
        return []


def _parse_name(title: str) -> tuple[str, str]:
    """'Jane Doe - ML Engineer at OpenAI | LinkedIn' -> ('Jane', 'Doe')"""
    name_part = re.split(r"\s*[-|–]\s*", title)[0].strip()
    parts = name_part.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return name_part, ""


def _extract_role(text: str) -> str:
    m = re.search(
        r"(Engineer|Researcher|Scientist|Manager|Director|Lead|Head|VP|CEO|CTO|"
        r"Product Manager|Designer|Analyst|Developer)[^|,\n-]{0,40}",
        text, re.I,
    )
    return m.group(0).strip() if m else ""


def search_candidates(company: str, role_keywords: str, limit: int = 20) -> list[dict]:
    """
    Search Google and Google Scholar for candidates at `company` matching `role_keywords`.
    Returns a list of candidate dicts ready for db.add_candidate().
    """
    candidates: list[dict] = []
    seen_urls: set[str] = set()

    queries = [
        f'site:linkedin.com/in/ "{company}" "{role_keywords}"',
        f'site:linkedin.com/in/ "{company}" {role_keywords}',
        f'"{company}" {role_keywords} -site:linkedin.com',
        # Google Scholar for researchers
        f'"{company}" {role_keywords} site:scholar.google.com',
        f'"{company}" {role_keywords} site:arxiv.org author',
    ]

    for query in queries:
        if len(candidates) >= limit:
            break
        results = _search(query, num=10)
        for r in results:
            if len(candidates) >= limit:
                break
            url     = r.get("link", "")
            title   = r.get("title", "")
            snippet = r.get("snippet", "")

            if url in seen_urls or not title:
                continue
            seen_urls.add(url)

            first, last = _parse_name(title)
            role_hint   = _extract_role(title + " " + snippet)

            candidates.append({
                "name":        f"{first} {last}".strip(),
                "first_name":  first,
                "last_name":   last,
                "company":     company,
                "role":        role_hint or role_keywords,
                "email":       "",
                "linkedin_url": url if "linkedin.com/in/" in url else "",
                "source_url":  url,
                "bio":         snippet[:500],
            })

    return candidates
