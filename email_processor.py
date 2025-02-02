import imaplib
import email
import datetime
import time
import sys
from email.utils import parsedate_to_datetime
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER
from utils import load_json_file, save_json_file

def extract_email_body(msg):
    """Extract plain text body from an email message, handling encoding errors."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except UnicodeDecodeError:
                    return part.get_payload(decode=True).decode("latin-1", errors="replace")
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return msg.get_payload(decode=True).decode("latin-1", errors="replace")
    return ""

def contains_job_keyword(subject, body):
    """Check if job-related terms are in the subject or body."""
    job_keywords = ["job", "hiring", "opportunity", "position", "role", "opening", "career", "developer", "engineer", "recruiter"]
    return any(keyword in subject.lower() or keyword in body.lower() for keyword in job_keywords)

def fetch_recent_recruiter_emails():
    """Fetch all emails from the last 4 days, ensuring job-related emails are processed immediately."""
    print("📩 Connecting to Yahoo Mail...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

    print("📥 Selecting inbox...")
    status, messages = mail.select("inbox")
    if status != "OK":
        print("❌ Error: Could not select inbox.")
        return []

    print("🔍 Searching for all emails from the last 4 days...")
    _, search_data = mail.search(None, "ALL")  
    email_ids = list(reversed(search_data[0].split()))  # Reverse to process newest emails first
    print(f"📨 Found {len(email_ids)} emails.")

    if not email_ids:
        print("✅ No emails to process.")
        return []

    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today - datetime.timedelta(days=4)

    print("📡 Fetching email headers (real-time processing, batching newest first)...")

    batch_size = 20  
    total_emails = len(email_ids)
    
    for start in range(0, total_emails, batch_size):
        batch = email_ids[start:start + batch_size]  
        print(f"📡 Processing batch {start + 1}-{min(start + batch_size, total_emails)} of {total_emails}... ", end="")
        sys.stdout.flush()

        try:
            _, msg_data = mail.fetch(",".join(e_id.decode() for e_id in batch), "(RFC822)")  
        except imaplib.IMAP4.error:
            print("⚠️ IMAP error while fetching emails. Retrying after 10 seconds...")
            time.sleep(10)
            continue  

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                sender = msg["From"]
                subject = msg["Subject"]
                body = extract_email_body(msg)

                if "Date" in msg:
                    try:
                        email_date = parsedate_to_datetime(msg["Date"]).replace(tzinfo=None)
                    except Exception:
                        print(f"⚠️ Could not parse date for email from {sender}. Skipping.")
                        continue

                    if email_date > today or email_date < cutoff_date:
                        continue  

                    # Ensure email visibility logic
                    if contains_job_keyword(subject, body) or "remote" in body.lower():
                        print(f"📖 Processing Job Email: {email_date.strftime('%Y-%m-%d %H:%M:%S')} - {subject} (From: {sender})")
                        print(f"📜 Full Email Body: {body[:500]}...")  # Preview first 500 chars of body
                        yield email_date, sender, subject, body  # Process job email immediately
                    else:
                        print(f"📖 Skipping Non-Job Email: {email_date.strftime('%Y-%m-%d %H:%M:%S')} - {subject} (From: {sender})")

        for _ in range(3):
            print(".", end="", flush=True)
            time.sleep(0.5)
        print()  
