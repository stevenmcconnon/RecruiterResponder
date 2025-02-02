import json
import os

def load_json_file(filename):
    """Load JSON data from a file, or return an empty dictionary if the file does not exist."""
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return {}

def save_json_file(filename, data):
    """Save JSON data to a file."""
    with open(filename, "w") as file:
        json.dump(data, file)

def clear_skipped_emails():
    """Manually reset skipped emails cache if requested."""
    confirm = input("⚠️ Are you sure you want to reset the skipped emails cache? (Y/N): ").strip().lower()
    if confirm == "y":
        save_json_file("skipped_emails.json", {})
        print("✅ Skipped emails cache has been cleared.")
    else:
        print("❌ Skipped emails cache was NOT cleared.")
