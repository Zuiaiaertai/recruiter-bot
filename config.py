import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
SERPER_API_KEY     = os.getenv("SERPER_API_KEY")
HUNTER_API_KEY     = os.getenv("HUNTER_API_KEY")
CALENDLY_EVENT_URL = os.getenv("CALENDLY_EVENT_URL", "")
GMAIL_CREDS_PATH   = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials/credentials.json")
GMAIL_TOKEN_PATH   = os.getenv("GMAIL_TOKEN_PATH", "credentials/token.json")
SENDER_EMAIL       = os.getenv("SENDER_EMAIL")
RECRUITER_NAME     = os.getenv("RECRUITER_NAME", "Recruiter")
RECRUITER_TITLE    = os.getenv("RECRUITER_TITLE", "Talent Partner")
RECRUITER_COMPANY  = os.getenv("RECRUITER_COMPANY", "Company")
