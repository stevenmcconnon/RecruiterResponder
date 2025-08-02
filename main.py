from email_processor import *
from email_responder import *
from utils import load_json_file, save_json_file
import datetime
from email.header import decode_header

SKIPPED_EMAILS = "skipped_emails.json"
SENT_EMAILS = "sent_emails.json"  # Track sent emails to prevent duplicates



def decode_subject(subject):
    """Decodes a MIME/Base64 encoded subject into plain text."""
    decoded_parts = decode_header(subject)
    decoded_subject = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_subject += part.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded_subject += part  # Already a string

    return decoded_subject.strip()

def process_recruiter_emails():
    """Fetch and process recruiter emails immediately instead of storing them for later."""
    print("🚀 Starting email processing...")
    
    skipped_emails = load_json_file(SKIPPED_EMAILS)
    sent_emails = load_json_file(SENT_EMAILS)

    # Fetch emails and process them one at a time
    for email_date, sender, subject, body in fetch_recent_recruiter_emails():
        email_id = f"{email_date} - {sender}"
        subject = decode_subject(subject)

        # **Stop displaying permanently skipped emails**
        if email_id in skipped_emails:
            continue  # No log, no processing

        # **Prevent sending multiple emails in a row (must be back-and-forth conversation)**
        if sender in sent_emails and not recruiter_has_replied(sender, email_date):
            print(f"🔄 Awaiting recruiter response for: {subject} (From: {sender}). Skipping.")
            continue

        print(f"\n📩 Processing Email: {email_date.strftime('%Y-%m-%d %H:%M:%S')} - {subject} (From: {sender})")

        if not check_subject_first(subject):
            print(f"🚫 Ignoring non-job-related email: {subject}")
            continue

        # Step 2: Extract rate and location before generating response
        rate, location = extract_rate_location(subject, body)

        # Step 3: Generate response only if it’s a valid job email
        response = generate_response(subject, body, sender)

        # Skip non-tech recruiter emails
        if response is None:
            continue

        print("\n=========================")
        print(f"📨 New recruiter email from: {sender}")
        print(f"📌 Subject: {subject}")
        print(f"🕒 Received at: {email_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📌 Body: {body}")

        print("\n💬 Generated Response:\n")
        print(response)
        print("\n=========================")

        # Prompt for response options immediately
        user_input = input("✅ Send this response? (Y/N/S/M): ").strip().lower()
        if user_input == "y":
            send_email(sender, "Re: " + subject, response, attach_resume=True)
            sent_emails[sender] = email_date.strftime('%Y-%m-%d %H:%M:%S')  # Convert datetime to string
            save_json_file(SENT_EMAILS, sent_emails)
        elif user_input == "m":
            manual_response = input("✍️ Enter your custom response: ")
            send_email(sender, "Re: " + subject, manual_response, attach_resume=True)
            sent_emails[sender] = email_date.strftime('%Y-%m-%d %H:%M:%S')  # Convert datetime to string
            save_json_file(SENT_EMAILS, sent_emails)
        elif user_input == "n":
            print("🚫 Email permanently skipped.")
            skipped_emails[email_id] = True
            save_json_file(SKIPPED_EMAILS, skipped_emails)
        elif user_input == "s":
            print("⏳ Skipping this email temporarily.")
        else:
            print("❌ Invalid input. Email skipped.")

def recruiter_has_replied(sender, current_email_date):
    """Checks if a recruiter has replied since the last response."""
    sent_emails = load_json_file(SENT_EMAILS)
    last_sent_date_str = sent_emails.get(sender)

    # If there's no prior sent email, assume first interaction
    if not last_sent_date_str:
        return True

    # Convert stored date string back to datetime for comparison
    last_sent_date = datetime.datetime.strptime(last_sent_date_str, '%Y-%m-%d %H:%M:%S')

    # If the current email is newer than the last sent email, recruiter has replied
    return current_email_date > last_sent_date

if __name__ == "__main__":
    process_recruiter_emails()
