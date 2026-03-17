"""
Email discovery via Hunter.io API with pattern-guessing fallback.
"""
import requests
from config import HUNTER_API_KEY

HUNTER_BASE = "https://api.hunter.io/v2"

KNOWN_DOMAINS: dict[str, str] = {
    "openai":          "openai.com",
    "anthropic":       "anthropic.com",
    "google":          "google.com",
    "deepmind":        "deepmind.com",
    "google deepmind": "deepmind.com",
    "meta":            "meta.com",
    "microsoft":       "microsoft.com",
    "apple":           "apple.com",
    "amazon":          "amazon.com",
    "netflix":         "netflix.com",
    "deepseek":        "deepseek.com",
    "bytedance":       "bytedance.com",
    "xai":             "x.ai",
    "mistral":         "mistral.ai",
    "cohere":          "cohere.com",
    "hugging face":    "huggingface.co",
    "stability ai":    "stability.ai",
}


def _domain(company: str) -> str:
    key = company.lower().strip()
    if key in KNOWN_DOMAINS:
        return KNOWN_DOMAINS[key]
    # best-effort guess
    slug = key.replace(" ", "")
    return f"{slug}.com"


def find_email_hunter(first: str, last: str, company: str) -> str | None:
    if not HUNTER_API_KEY or not first or not last:
        return None
    try:
        r = requests.get(
            f"{HUNTER_BASE}/email-finder",
            params={"domain": _domain(company), "first_name": first,
                    "last_name": last, "api_key": HUNTER_API_KEY},
            timeout=10,
        )
        data = r.json().get("data", {})
        email = data.get("email")
        score = data.get("score", 0)
        return email if email and score >= 40 else None
    except Exception as e:
        print(f"  [email_finder] Hunter error: {e}")
        return None


def guess_patterns(first: str, last: str, company: str) -> list[str]:
    d = _domain(company)
    f, l = first.lower(), last.lower()
    return [
        f"{f}.{l}@{d}",
        f"{f}{l}@{d}",
        f"{f[0]}{l}@{d}",
        f"{f}@{d}",
        f"{f[0]}.{l}@{d}",
    ]


def find_email(first: str, last: str, company: str) -> str | None:
    """Try Hunter.io, fall back to most common pattern guess."""
    email = find_email_hunter(first, last, company)
    if email:
        return email
    guesses = guess_patterns(first, last, company)
    return guesses[0] if guesses else None
