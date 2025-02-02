import smtplib
import os
import openai
import json
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, RESUME_PATH, OPENAI_API_KEY
from utils import save_json_file, load_json_file

SKIPPED_EMAILS = "skipped_emails.json"  # Store permanently skipped emails

def clean_html(raw_html):
    """Remove HTML tags and extract plain text from an email body."""
    clean_text = re.sub(r'<.*?>', '', raw_html)  # Remove HTML tags
    return clean_text.strip()

def extract_rate_location(email_subject, email_body, sender):
    """Extract pay rate, job location, and determine if email is tech-related using OpenAI."""

    # Clean HTML if present
    cleaned_body = clean_html(email_body)

    prompt = f"""
    Analyze the following email content and subject. 
    
    1. Determine if this is a job opportunity email from a **tech recruiter** (Software, DevOps, AI, Data, etc.). 
       If it is **NOT a tech recruiter email**, return `"not_related": true`.
    
    2. If it **IS** a tech recruiter email, extract the **pay rate** (in USD) and **job location**.

    Subject: {email_subject}

    Full Email Content:
    {cleaned_body}

    Ensure the response is a **JSON object** formatted like this:
    {{
        "rate": "XX/hr" (or "Unknown" if missing),
        "location": "Remote" or "City, State" or "On-Site" (or "Unknown" if missing),
        "not_related": true (if this is NOT a tech recruiter email, otherwise false)
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content.strip()
        print(f"📝 Raw API Response: {result}")  # Log full response

        # Clean JSON response and parse it correctly
        extracted_data = json.loads(re.sub(r"```json|```", "", result).strip())

        # **If it's not a tech recruiter email, mark it as permanently skipped**
        if extracted_data.get("not_related", False):
            print("🚫 Email is **not tech-related**. Marking as permanently skipped.")
            skipped_emails = load_json_file(SKIPPED_EMAILS)
            skipped_emails[f"{email_subject} - {sender}"] = True  # Mark as skipped
            save_json_file(SKIPPED_EMAILS, skipped_emails)
            return "Not Related", "Not Related"

        rate = extracted_data.get("rate", "Unknown")
        location = extracted_data.get("location", "Unknown")
        
        print(f"📊 Extracted Rate: {rate} | 📍 Location: {location}")
        return rate, location
    except Exception as e:
        print(f"❌ Failed to extract rate/location: {e}")
        return "Unknown", "Unknown"

def generate_response(subject, body, sender):
    """Generate a response based on extracted job details."""
    rate, location = extract_rate_location(subject, body, sender)

    if rate == "Not Related" and location == "Not Related":
        return None  # Skip non-tech recruiter emails

    if location and "on-site" in location.lower():
        response = (
            f"Hello,\n\n"
            "I noticed this position is listed as on-site. Would remote work be an option for this role?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif location and location != "Remote" and location != "Unknown":
        response = (
            f"Hello,\n\n"
            f"I see this position is in {location}. Would remote work be an option?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif location != "Unknown" and rate == "Unknown":
        response = (
            f"Hello,\n\n"
            f"I see this position is in {location}. Can you confirm the pay rate?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif rate != "Unknown" and location == "Unknown":
        response = (
            f"Hello,\n\n"
            f"The listed pay rate is {rate}. Can you confirm if remote work is an option?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif rate != "Unknown" and location != "Unknown":
        response = (
            f"Hello,\n\n"
            f"I see this opportunity is in {location} with a pay rate of {rate}. Can we discuss further?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    else:
        response = (
            "Hello,\n\n"
            "Please tell me two things:\n"
            "1. Is the position fully remote?\n"
            "2. How much does the position pay?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )

    return response




def send_email(recipient, subject, body, attach_resume=False):
    """Send an email response after confirmation."""
    print(f"📤 Sending email to {recipient}...")

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if attach_resume and os.path.exists(RESUME_PATH):
            with open(RESUME_PATH, "rb") as file:
                resume_attachment = MIMEText(file.read(), "base64", "utf-8")
                resume_attachment.add_header("Content-Disposition", f"attachment; filename={os.path.basename(RESUME_PATH)}")
                msg.attach(resume_attachment)

        print("📡 Connecting to Yahoo SMTP server...")
        with smtplib.SMTP_SSL(SMTP_SERVER, 465, timeout=30) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            print("✅ Logged in successfully. Sending email...")
            server.sendmail(EMAIL_ADDRESS, recipient, msg.as_string())
            print("✅ Email sent successfully.")

    except smtplib.SMTPException as e:
        print(f"❌ SMTP Error: {e}")
    except Exception as e:
        print(f"❌ General Error: {e}")
