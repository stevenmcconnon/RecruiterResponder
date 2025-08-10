import smtplib
import os
import json
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, RESUME_PATH

# Local LLM endpoint (optional). If unavailable, we fall back gracefully.
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# Decision thresholds (ask-first strategy)
ACCEPT_THRESHOLD = 85       # >= accept immediately
MIN_ACCEPTABLE_RATE = 75    # 75–85 -> light negotiation
REJECT_BELOW = 65           # <65 -> decline


def clean_html(raw_html: str) -> str:
    """Remove HTML tags and extract plain text from an email body."""
    if raw_html is None:
        return ""
    try:
        # Strip tags and collapse whitespace
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return raw_html or ""


def check_subject_first(email_subject, sender: str = "", email_body: str = "") -> bool:
    """
    Decide if the message looks like a direct recruiter/job email (True) vs.
    newsletter/marketing/sales outreach (False). Logs reasons verbosely.
    Backward compatible: you can call with just email_subject.
    """
    s_subject = (email_subject or "").lower()
    s_sender = (sender or "").lower()
    s_body = clean_html(email_body or "").lower()
    blob = " ".join([s_subject, s_sender, s_body])

    # Strong negatives: newsletters / job boards / marketing platforms
    job_board_domains = [
        "@dice.com", "@connect.dice.com", "@alerts.indeed.com", "@indeed.com",
        "@notifications.linkedin.com", "@linkedin.com", "@ziprecruiter.com",
        "@monster.com", "@glassdoor.com"
    ]
    marketing_platform_hints = [
        "mailchimp", "sendgrid", "constantcontact", "hubspot", "marketo",
        "pardot", "klaviyo", "mailgun", "sendinblue", "campaign", "mailer"
    ]
    marketing_sender_hints = [
        "noreply", "no-reply", "donotreply", "info@", "sales@", "marketing@",
        "newsletter@", "support@", "hello@", "team@", "updates@", "alerts@", "notifications@"
    ]
    newsletter_phrases = [
        "unsubscribe", "manage preferences", "view in browser",
        "knowledge center", "digest", "job alert", "recommended jobs",
        "intellisearch alert", "terms & conditions", "privacy policy"
    ]

    # Negatives: solar/retail sales outreach cues
    solar_terms = [
        "solar", "photovoltaic", "pv", "panel", "site survey", "proposal",
        "estimate", "quote", "kwh", "net metering", "nem", "utility bill",
        "pge", "pg&e", "roof", "installer", "powerwall", "inverter"
    ]
    sales_cta = [
        "schedule a call", "book a call", "book time", "get a quote", "free estimate",
        "demo", "webinar", "limited time", "discount", "promo", "promotion", "save"
    ]

    # Positives: recruiter/job outreach cues
    strong_pos = ["recruiter", "talent acquisition", "sourcer", "hiring manager"]
    medium_pos = [
        "contract", "contract-to-hire", "c2c", "w2", "1099", "interview",
        "open role", "opening", "role", "position", "rate", "bill rate", "pay rate"
    ]

    score = 0
    reasons = []

    # Positives
    if any(p in blob for p in strong_pos):
        score += 3
        reasons.append("strong recruiter cue")
    if any(p in blob for p in medium_pos):
        score += 1
        reasons.append("job terms")
    # numeric rate with hr/hour nearby
    if re.search(r"\$?\s*\d+(?:\.\d{1,2})?\s*/?\s*(?:hr|hour)\b", blob):
        score += 1
        reasons.append("rate w/ hr")

    # Negatives (heavier)
    if any(d in s_sender for d in job_board_domains):
        score -= 3
        reasons.append("job board domain")
    if any(h in s_sender for h in marketing_sender_hints):
        score -= 2
        reasons.append("marketing-y sender")
    if any(p in blob for p in marketing_platform_hints):
        score -= 2
        reasons.append("marketing platform")
    if any(p in blob for p in newsletter_phrases):
        score -= 2
        reasons.append("newsletter phrasing")
    if any(p in blob for p in sales_cta):
        score -= 2
        reasons.append("sales CTA")
    if any(p in blob for p in solar_terms):
        score -= 3
        reasons.append("solar/retail sales")

    is_job = score > 0
    print(f"[classifier] job_related={is_job} score={score} reasons={reasons}")
    return is_job


def extract_rate_location(email_subject: str, email_body: str):
    """
    Extract a human-readable pay rate and location from the message using regex heuristics.
    Returns (rate_str, location_str). If unknown, returns 'Unknown'.
    """
    text = f"{email_subject or ''} \n {clean_html(email_body or '')}".lower()

    # Rate detection: handle ranges like $80-90/hr, 80–90/hour, $85/hr
    rate_match = re.search(
        r"(\$?\s*\d+(?:\.\d{1,2})?)\s*(?:[-–]\s*\$?\s*\d+(?:\.\d{1,2})?)?\s*/?\s*(?:hr|hour)\b",
        text
    )
    rate_str = "Unknown"
    if rate_match:
        span_text = rate_match.group(0)
        # normalize spacing
        rate_str = re.sub(r"\s+", "", span_text).replace("hour", "hr")

    # Location detection
    location = "Unknown"
    if "remote" in text:
        location = "Remote"
    elif "hybrid" in text:
        location = "Hybrid"
    elif "onsite" in text or "on-site" in text or "on site" in text:
        location = "On-Site"
    else:
        # Try to capture patterns like "San Jose, CA" or "Austin, TX"
        m_city = re.search(
            r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*),\s*([A-Z]{2})\b",
            clean_html(email_body or "")
        )
        if m_city:
            location = f"{m_city.group(1)}, {m_city.group(2)}"

    return rate_str, location


def generate_response(email_subject, email_body, sender):
    """
    Generate an AI response for a recruiter email using Ollama when available.
    - Never raises: always returns a string ("" means 'skip sending').
    - Verbose logging for HTTP/JSON/other failures.
    - Deterministic fallback reply if the LLM call fails or returns nothing.
    """
    # Early guard: never respond to newsletters / job alerts / sales/marketing
    if check_subject_first(email_subject, sender, email_body) is False:
        print("ℹ️ Skipping auto-reply: newsletter/marketing/sales detected.")
        return ""  # caller should treat empty as 'do not send'

    def _fallback_template_reply(subject, body, from_addr, error_info=None):
        # Attempt to extract metadata
        try:
            rate, location = extract_rate_location(subject, body)
        except Exception:
            rate, location = "Unknown", "Unknown"

        # Parse numeric rate (first number found)
        numeric_rate = None
        m = re.search(r"\$?\s*([0-9]+(?:\.[0-9]{1,2})?)", rate or "")
        if m:
            try:
                numeric_rate = float(m.group(1))
            except Exception:
                numeric_rate = None

        details_request = (
            "- Role title and team\n"
            "- Tech stack and responsibilities\n"
            "- Fully-remote vs. hybrid/on-site expectations (I prefer fully remote)\n"
            "- Contract length, W2/1099/C2C\n"
            "- Hourly rate range, interview process, expected start\n"
        )

        # Ask-first logic mirrors the LLM rules
        if numeric_rate is None:
            body_text = f"""Hi {from_addr or 'there'},

Thanks for reaching out—I'm interested. Could you share the hourly rate or range, plus a few details?
{details_request}

Best,
Steven
"""
        elif numeric_rate >= ACCEPT_THRESHOLD:
            body_text = f"""Hi {from_addr or 'there'},

Thanks for the details. That rate works for me. I'm fully remote and available after 11am PT (Mon–Fri).
Could you also share interview steps and expected start?

Best,
Steven
"""
        elif numeric_rate >= MIN_ACCEPTABLE_RATE:
            body_text = f"""Hi {from_addr or 'there'},

Thanks for the info—I prefer fully remote. Is there any flexibility on rate?
If not, I can still proceed depending on scope and contract length. Could you share interview steps and start?

Best,
Steven
"""
        elif numeric_rate >= REJECT_BELOW:
            body_text = f"""Hi {from_addr or 'there'},

Thanks for the details. I usually need to be at least ${MIN_ACCEPTABLE_RATE}/hr for this scope.
If the budget can move, I'm open to continue; otherwise I may need to pass.

Best,
Steven
"""
        else:
            body_text = f"""Hi {from_addr or 'there'},

Thanks for considering me. The current budget is below what I can accept for this scope, so I’ll pass.
If things change, I’m happy to revisit.

Best,
Steven
"""
        # Verbose log (not emailed)
        if error_info:
            try:
                print("⚠️ Fallback invoked: Ollama response failed. Verbose error info:")
                print(json.dumps(error_info, indent=2))
            except Exception:
                print("⚠️ Fallback invoked; error_info could not be serialized.")
        return body_text

    # Construct prompt for LLM (ask-first behavior)
    prompt = f"""
You are writing an email reply AS "Steven" to the ORIGINAL SENDER of the message below.
Short, direct, professional. Do NOT summarize job listings.

Behavior:
- If the message already states an hourly rate (or range), apply these rules:
  • If rate ≥ ${ACCEPT_THRESHOLD}/hr: ACCEPT and confirm availability after 11am PT (Mon–Fri).
  • If ${MIN_ACCEPTABLE_RATE}–${ACCEPT_THRESHOLD}/hr: ask (briefly) if there’s flexibility; otherwise proceed if remote.
  • If ${REJECT_BELOW}–${MIN_ACCEPTABLE_RATE}/hr: ask if budget can move to ${MIN_ACCEPTABLE_RATE}/hr; otherwise pause.
  • If < ${REJECT_BELOW}/hr: politely decline due to budget.
- If NO rate is stated: ASK for the hourly rate or range first (do NOT propose a target).
Always mention preference for fully-remote roles. Keep it concise and sign as "Steven".

Subject: {email_subject}
From: {sender}
Email (plain text):
{clean_html(email_body)}
"""

    # Try Ollama, but never crash if it fails
    try:
        payload = {"model": "mistral", "prompt": prompt, "stream": False}
        response = requests.post(OLLAMA_URL, json=payload, timeout=25)

        if response is None:
            raise RuntimeError("No response object returned from requests.post().")

        status = response.status_code
        text_snippet = response.text[:600] if response.text else ""

        if status < 200 or status >= 300:
            raise RuntimeError(f"Ollama HTTP {status}: {text_snippet}")

        try:
            data = response.json()
        except Exception as je:
            raise RuntimeError(f"Invalid JSON from Ollama: {je}; raw: {text_snippet}")

        model_text = (data.get("response") or data.get("text") or "").strip()
        if not model_text:
            raise RuntimeError(f"Empty LLM response payload. JSON keys: {list(data.keys())}")

        return model_text

    except Exception as e:
        # Build verbose error info
        err_info = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "ollama_url": OLLAMA_URL,
        }
        try:
            err_info["status_code"] = response.status_code if 'response' in locals() and response is not None else None
            err_info["raw_response_snippet"] = response.text[:600] if 'response' in locals() and response is not None else None
        except Exception:
            pass
        try:
            import traceback as _tb
            err_info["traceback"] = "".join(_tb.format_exc())
        except Exception:
            err_info["traceback"] = "Traceback unavailable"

        # Log verbose error and return fallback
        try:
            print("❌ Error generating response (verbose):")
            print(json.dumps(err_info, indent=2))
        except Exception:
            print(f"❌ Error generating response (unserializable error object): {e}")

        return _fallback_template_reply(email_subject, email_body, sender, error_info=err_info)


def send_email(recipient_email, subject, body):
    """Send an email response to a recruiter.
    If body is empty/whitespace, skip sending (prevents replies to newsletters/marketing).
    """
    try:
        if not body or not str(body).strip():
            print("ℹ️ Not sending email: empty body (treated as skip).")
            return

        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = recipient_email
        msg["Subject"] = subject

        # Plain-text body
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Optional resume attachment
        if RESUME_PATH and os.path.exists(RESUME_PATH):
            with open(RESUME_PATH, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="octet-stream")
                attachment.add_header("Content-Disposition", "attachment", filename=os.path.basename(RESUME_PATH))
                msg.attach(attachment)

        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())

        print(f"📧 Email sent successfully to {recipient_email}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")