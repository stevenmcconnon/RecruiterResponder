import os

# Email Credentials
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# SMTP/IMAP Server Details
SMTP_SERVER = "smtp.mail.yahoo.com"
IMAP_SERVER = "imap.mail.yahoo.com"

# OpenAI API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Resume File Path
RESUME_PATH = "Steven_McConnon_Resume.pdf"

# File Paths for Caching and Tracking
CONVERSATION_TRACKER = "recruiter_conversations.json"
EMAIL_CACHE = "email_cache.json"
SKIPPED_EMAILS = "skipped_emails.json"
INTERVIEW_CSV = "upcoming_interviews.csv"
