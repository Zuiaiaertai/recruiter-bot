"""
Classify inbound candidate replies using Claude Haiku (fast + cheap).
"""
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

CATEGORIES = ["interested", "not_interested", "scheduling", "question",
              "out_of_office", "other"]


def classify_reply(email_body: str, candidate_name: str) -> str:
    """
    Returns one of: interested | not_interested | scheduling |
                    question   | out_of_office  | other
    """
    prompt = f"""Classify this recruiter email reply from {candidate_name}.

Email:
\"\"\"
{email_body[:800]}
\"\"\"

Categories:
- interested      : open to the opportunity, wants to learn more
- not_interested  : declining or explicitly not looking
- scheduling      : trying to book a time or asking about availability
- question        : asking a specific question about role/company/comp
- out_of_office   : auto-reply or OOO message
- other           : unclear or unrelated

Reply with ONLY the category name, nothing else."""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    result = msg.content[0].text.strip().lower()
    return result if result in CATEGORIES else "other"
