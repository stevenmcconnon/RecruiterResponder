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

NEGOTIATE_THRESHOLD = 85
MIN_ACCEPTABLE_RATE = 75
HOURS_PER_YEAR = 2080  # 40 hours per week * 52 weeks

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

    1. Determine if this is a job opportunity email from a **tech recruiter** (Software, DevOps, AI, Data, etc.), even if it is informal or conversational.
       If it is **NOT a tech recruiter email**, return `"not_related": true`.

    2. If it **IS** a tech recruiter email, extract the **pay rate** (in USD) and **job location**.

    3. If the email is from a recruiter and they are asking for a resume, **always classify as job-related**.

    Subject: {email_subject}

    Full Email Content:
    {cleaned_body}

    Ensure the response is a **JSON object** formatted like this:
    {{
        "rate": "XX/hr" (or "Unknown" if missing),
        "location": "Remote" or "City, State" or "On-Site" (or "Unknown" if missing),
        "not_related": true (if this is NOT a tech recruiter email, otherwise false),
        "requires_resume": true (if the email asks for a resume, otherwise false),
        "classification_reason": "Brief explanation of why this email was classified this way"
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
            reason = extracted_data.get("classification_reason", "No reason provided.")
            print(f"🚫 Email is **not tech-related** (Reason: {reason}). Marking as permanently skipped.")
            skipped_emails = load_json_file(SKIPPED_EMAILS)
            skipped_emails[f"{email_subject} - {sender}"] = True  # Mark as skipped
            save_json_file(SKIPPED_EMAILS, skipped_emails)
            return "Not Related", "Not Related"

        # **If the email explicitly asks for a resume, always process it**
        if extracted_data.get("requires_resume", False):
            print(f"📌 Recruiter explicitly requested a resume. Ensuring response.")
            return "Resume Requested", "Unknown"

        rate = extracted_data.get("rate", "Unknown")
        location = extracted_data.get("location", "Unknown")
        
        print(f"📊 Extracted Rate: {rate} | 📍 Location: {location}")
        return rate, location
    except Exception as e:
        print(f"❌ Failed to extract rate/location: {e}")
        return "Unknown", "Unknown"



def convert_salary_to_hourly(salary_str):
    """Convert yearly salary to hourly rate assuming 40 hours per week."""
    try:
        salary = int(re.search(r'\d+', salary_str).group())
        hourly_rate = round(salary / HOURS_PER_YEAR, 2)
        return hourly_rate
    except (AttributeError, ValueError):
        return None  # If parsing fails, return None




def generate_response(subject, body, sender):
    """Generate a response based on extracted job details, including rate negotiation."""
    rate, location = extract_rate_location(subject, body, sender)  # Ensure sender is passed

    # Convert salary to hourly rate if needed
    if "/year" in rate.lower():
        rate_value = convert_salary_to_hourly(rate)
    else:
        try:
            rate_value = int(re.search(r'\d+', rate).group()) if rate != "Unknown" else None
        except AttributeError:
            rate_value = None

    if rate == "Not Related" and location == "Not Related":
        return None  # Skip non-tech recruiter emails

    if rate == "Resume Requested":
        response = (
            f"Hello,\n\n"
            "Thank you for reaching out! Please find my resume attached.\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif rate_value is not None and rate_value < MIN_ACCEPTABLE_RATE:
        response = (
            f"Hello,\n\n"
            f"Thank you for reaching out. I'm interested in this opportunity, but my minimum rate is ${MIN_ACCEPTABLE_RATE}/hr.\n\n"
            "Would there be flexibility to adjust the compensation to align with this?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif rate_value is not None and MIN_ACCEPTABLE_RATE <= rate_value < NEGOTIATE_THRESHOLD:
        response = (
            f"Hello,\n\n"
            f"I appreciate the offer. I'm interested, but I typically work at a rate of ${NEGOTIATE_THRESHOLD}/hr.\n\n"
            "Would it be possible to adjust the compensation accordingly?\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif rate_value is not None and rate_value >= NEGOTIATE_THRESHOLD:
        response = (
            f"Hello,\n\n"
            "The rate meets my expectations, and I would be happy to proceed.\n\n"
            "Please let me know the next steps.\n\n"
            "Warm Regards,\n\n"
            "Steven McConnon\n"
            "407-733-0570"
        )
    elif location and "on-site" in location.lower():
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
