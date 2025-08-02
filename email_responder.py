import smtplib
import os
import json
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, RESUME_PATH

# Ollama API URL
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

SKIPPED_EMAILS = "skipped_emails.json"

NEGOTIATE_THRESHOLD = 85
MIN_ACCEPTABLE_RATE = 75
HOURS_PER_YEAR = 2080

def clean_html(raw_html):
    """Remove HTML tags and extract plain text from an email body."""
    clean_text = re.sub(r'<.*?>', '', raw_html)
    return clean_text.strip()

import requests
import json

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

def check_subject_first(email_subject):
    """Determine if the email subject is job-related using the Mistral model via Ollama."""
    prompt = f"""
    I am a software engineer. Your task is to decide whether an email **subject line** belongs to a job opportunity from a recruiter.

    **Classification Rules:**
    - **job_related = true** → ONLY if the subject clearly mentions job openings, interviews, recruiter messages, or hiring opportunities.
    - **job_related = false** → If it's a receipt, advertisement, finance, subscription, bill, newsletter, bank alert, or spam.

    **Subject:** "{email_subject}"

    **Response Format (strict JSON, no extra text):**
    {{
        "job_related": true or false
    }}
    """

    try:
        response = requests.post(OLLAMA_URL, json={"model": "mistral", "prompt": prompt}, stream=True)

        # Collect response chunks and assemble full response
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_chunk = json.loads(line.decode("utf-8"))
                    if "response" in json_chunk:
                        full_response += json_chunk["response"]
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON Decode Error while reading stream: {e}")
                    continue  # Skip invalid chunks

        # Check for an empty response
        full_response = full_response.strip()
        if not full_response:
            print("⚠️ Empty response received from Ollama.")
            return None
        
        # Debugging: Print full response before parsing
        print(f"🔍 Full response from Ollama:\n{full_response}")

        # Ensure we properly extract the expected boolean flag
        extracted_data = json.loads(full_response)

        return extracted_data.get("job_related", False)
    
    except Exception as e:
        print(f"⚠️ Failed to analyze subject with Ollama: {e}")
        return None


def extract_rate_location(email_subject, email_body):
    """Extract pay rate and job location using Ollama."""
    cleaned_body = clean_html(email_body)

    prompt = f"""
    I am a software engineer who gets many tech recruiter emails. Your task:
    
    1️⃣ **Confirm if this is a job opportunity from a recruiter.**
    2️⃣ **Extract the pay rate (in USD per hour) and job location (Remote, City/State, or On-Site).**
    
    If the email **is not job-related**, set `"not_related": true` and leave `"rate"` and `"location"` as `"Unknown"`.

    **Subject:** {email_subject}
    **Email Content:** {cleaned_body}

    **Strict JSON Response (NO EXTRA TEXT):**
    {{
        "rate": "XX",   
        "location": "Remote" or "City, State" or "On-Site" or "Unknown",
        "not_related": true or false
    }}
    """

    try:
        response = requests.post(OLLAMA_URL, json={"model": "mistral", "prompt": prompt}, stream=True)

        # Collect and reconstruct response properly
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_chunk = json.loads(line.decode("utf-8"))
                    if "response" in json_chunk:
                        full_response += json_chunk["response"]
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON Decode Error while reading stream: {e}")
                    continue

        full_response = full_response.strip()
        if not full_response:
            print("⚠️ Empty response received from Ollama.")
            return "Unknown", "Unknown"
        
        print(f"🔍 Full response from Ollama:\n{full_response}")

        # Ensure we only parse valid JSON
        extracted_data = json.loads(full_response)

        # If it's not job-related, return early
        if extracted_data.get("not_related", False):
            return "Not Related", "Not Related"

        # Extract rate and location safely
        rate = extracted_data.get("rate", "Unknown")
        location = extracted_data.get("location", "Unknown")

        return rate, location
    except Exception as e:
        print(f"❌ Failed to extract rate/location: {e}")
        return "Unknown", "Unknown"



def generate_response(email_subject, email_body, sender):
    """Generate an AI response for a recruiter email using Ollama."""
    prompt = f"""
    Read the following **job-related email** and generate a polite, professional response.

    Subject: {email_subject}
    Sender: {sender}
    Email Content:
    {clean_html(email_body)}

    Respond with an **appropriate reply** formatted as an email response.
    """

    try:
        response = requests.post(OLLAMA_URL, json={"model": "mistral", "prompt": prompt})
        result = response.json().get("response", "Error generating response.")
        return result
    except Exception as e:
        print(f"❌ Error generating response: {e}")
        return "Error generating response."

def send_email(recipient_email, subject, body):
    """Send an email response to a recruiter."""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = recipient_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        if RESUME_PATH and os.path.exists(RESUME_PATH):
            with open(RESUME_PATH, "rb") as attachment:
                resume = MIMEText(attachment.read(), "base64", "utf-8")
                resume.add_header("Content-Disposition", "attachment", filename=os.path.basename(RESUME_PATH))
                msg.attach(resume)

        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())

        print(f"📧 Email sent successfully to {recipient_email}")

    except Exception as e:
        print(f"❌ Error sending email: {e}")
