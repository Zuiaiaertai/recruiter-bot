"""
Claude-powered email generation for outreach and replies.
"""
import anthropic
from config import (ANTHROPIC_API_KEY, RECRUITER_NAME, RECRUITER_TITLE,
                    RECRUITER_COMPANY, CALENDLY_EVENT_URL)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = (
    "You are an expert technical recruiter writing highly personalized, concise outreach emails. "
    "Your emails are warm, direct, and never sound like mass spam. "
    "Always reference specific details from the candidate's background. "
    "Keep initial outreach under 120 words. Never use hollow openers like "
    "'I came across your profile' or 'I hope this finds you well'. "
    "Write in plain text — no markdown, no bullet points."
)


def generate_outreach(candidate: dict, job_description: str) -> tuple[str, str]:
    """
    Generate personalized outreach email.
    Returns (subject, body).
    """
    prompt = f"""Write a recruiter outreach email for this candidate.

Candidate:
- Name: {candidate['name']}
- Company: {candidate['company']}
- Role/background: {candidate.get('role', 'N/A')}
- Bio snippet: {candidate.get('bio', 'N/A')[:300]}
- LinkedIn: {candidate.get('linkedin_url', 'N/A')}

Role we're hiring for:
{job_description}

Recruiter:
- Name: {RECRUITER_NAME}
- Title: {RECRUITER_TITLE}
- Company: {RECRUITER_COMPANY}
- Scheduling link: {CALENDLY_EVENT_URL}

Format:
SUBJECT: <subject line>

<email body>

Include the scheduling link naturally at the end if they're interested."""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()

    subject = ""
    body_lines = []
    past_subject = False
    for line in text.split("\n"):
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
            past_subject = True
        elif past_subject:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if not subject:
        subject = f"Opportunity at {RECRUITER_COMPANY}"

    return subject, body


def generate_reply(candidate: dict, job_description: str,
                   conversation: list[dict], reply_type: str) -> str:
    """
    Generate an auto-reply.
    reply_type: 'interested' | 'scheduling' | 'question' | 'followup'
    """
    history = "\n".join(
        f"{'[You]' if e['direction'] == 'out' else f'[{candidate[\"name\"]}]'}: "
        f"{e['body'][:300]}"
        for e in conversation[-6:]   # last 6 messages for context
    )

    task = {
        "interested": (
            f"The candidate is interested. Reply warmly, briefly express excitement, "
            f"and invite them to book a 30-min chat: {CALENDLY_EVENT_URL}"
        ),
        "scheduling": (
            f"The candidate wants to schedule. Confirm the link: {CALENDLY_EVENT_URL} "
            "or offer to coordinate directly if they prefer."
        ),
        "question": (
            "The candidate asked a question about the role or company. "
            "Answer concisely and keep them engaged."
        ),
        "followup": (
            "No reply in 5 days. Write a brief, non-pushy follow-up bump (2-3 sentences max). "
            "Keep it light — maybe mention something timely about the role."
        ),
    }.get(reply_type, "Write an appropriate professional reply.")

    prompt = f"""You are {RECRUITER_NAME}, a recruiter at {RECRUITER_COMPANY}.

Job context:
{job_description[:400]}

Conversation history:
{history}

Task: {task}

Write ONLY the reply body. Plain text, under 100 words."""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=250,
        system="You are a professional recruiter writing brief, warm email replies.",
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
