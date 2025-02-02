# 📧 Automated Email Responder for Job Inquiries

This project is an **AI-powered email automation system** designed to efficiently handle recruiter emails. It processes incoming emails, extracts key job details (rate, location, etc.), and generates intelligent responses based on predefined criteria.

## 🚀 Features  
✅ **Automatically detects job-related emails** and ignores non-relevant messages.  
✅ **Extracts job location and pay rate** from both the subject and email body using OpenAI.  
✅ **Handles "On-Site" jobs properly** by negotiating for remote work instead of asking if it's remote.  
✅ **Prompts for user confirmation before sending a response** (`Y/N/S/M` options).  
✅ **Sends responses with an attached resume** for relevant job opportunities.  
✅ **Skips permanently rejected emails** and removes them from future processing.  
✅ **Supports both plain text and HTML emails** (automatically cleans HTML for better extraction).  

## 🔧 How It Works  
1️⃣ Connects to your Yahoo Mail inbox via IMAP and scans recent emails.  
2️⃣ Identifies job-related emails and extracts **rate, location, and key details** using OpenAI.  
3️⃣ Prompts you to **approve, skip, or modify responses** before sending.  
4️⃣ Sends emails via **Yahoo SMTP** and logs interactions.  
5️⃣ Stores skipped and permanently rejected emails to avoid redundant processing.  

## 📂 File Structure  
- `main.py` – The main script that fetches and processes emails.  
- `email_processor.py` – Extracts job-related emails and prepares them for processing.  
- `email_responder.py` – Generates responses, formats messages, and sends emails.  
- `config.py` – Stores email credentials and API settings (use environment variables for security).  
- `utils.py` – Utility functions for logging, JSON storage, and cache handling.  

## 💡 Setup & Installation  

### **1️⃣ Clone the repository**  
```bash
git clone https://github.com/yourusername/email-auto-responder.git
cd email-auto-responder

### **2️⃣ Set up a virtual environment
```bash
python3 -m venv myenv  # Create a virtual environment
source myenv/bin/activate  # Activate it on macOS/Linux
myenv\Scripts\activate  # Activate it on Windows


### **3️⃣ Install dependencies
```bash
pip install -r requirements.txt


### **4️⃣ Set up environment variables
EMAIL_ADDRESS → Your Yahoo email
EMAIL_PASSWORD → Your Yahoo App Password (not your regular password)
OPENAI_API_KEY → Your OpenAI API key

### **5️⃣ Run the script
```bash
python main.py

