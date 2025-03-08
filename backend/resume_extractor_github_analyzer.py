import gradio as gr
import pandas as pd
import spacy
import re
import pdfplumber
import csv
import os
import requests  # Import the requests library

# Load NLP Model
nlp = spacy.load("en_core_web_sm")

# CSV File Name
csv_filename = "candidates.csv"
fieldnames = [
    "Full Name", "Last Name", "Email", "Phone Number", "Experience (Years)", 
    "Skills", "Courses Completed", "Education", "CGPA", "Location", 
    "Projects", "Language Proficiency"
]

# Ensure CSV Exists with Headers
if not os.path.exists(csv_filename):
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

# Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

# Extract GitHub Username from Text
def extract_github_username(text):
    github_url_pattern = r"github\.com/([a-zA-Z0-9-]+)"
    match = re.search(github_url_pattern, text)
    return match.group(1) if match else None

# Extract Resume Details
def extract_resume_details(text):
    sections = {
        "Full Name": "",
        "Last Name": "",
        "Email": "",
        "Phone Number": "",
        "Experience (Years)": 0,
        "Skills": [],
        "Courses Completed": [],
        "Education": [],
        "CGPA": "",
        "Location": "",
        "Projects": [],  # List of projects (name, language, description, URL)
        "Language Proficiency": {}  # Language proficiency (language: percentage)
    }

    current_section = None

    for line in text.split("\n"):
        line = line.strip()

        # Check for section headers
        if "Honors & Awards" in line:
            current_section = "Honors and Awards"
            continue
        elif "I am" in line:
            current_section = "Summary"
            continue
        elif "Certifications" in line:
            current_section = "Certifications"
            continue
        elif "Publications" in line:
            current_section = "Publications"
            continue
        elif "Experience" in line:
            current_section = "Experience Details"
            continue
        elif "Education" in line:
            current_section = "Education"
            continue
        elif "Skills" in line:
            current_section = "Skills"
            continue
        elif "Courses Completed" in line:
            current_section = "Courses Completed"
            continue
        elif "Hobbies" in line:
            current_section = "Hobbies"
            continue
        elif "Location" in line:
            current_section = "Location"
            continue

        # Assign lines to the current section
        if current_section:
            if line:  # Skip empty lines
                sections[current_section].append(line)

    # Convert lists to strings for CSV
    for key in sections:
        if isinstance(sections[key], list):
            sections[key] = ", ".join(sections[key])

    # Extract Name
    doc = nlp(text)
    name = "Unknown"
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name = ent.text
            break
    first_name, last_name = (name.split(" ")[0], " ".join(name.split(" ")[1:])) if " " in name else (name, "")
    sections["Full Name"] = name
    sections["Last Name"] = last_name

    # Extract Email
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    sections["Email"] = email_match.group(0) if email_match else "Not Found"

    # Extract Phone Number
    phone_match = re.search(r"\+?\d{10,15}", text)
    sections["Phone Number"] = phone_match.group(0) if phone_match else "Not Found"

    # Extract Experience
    experience_match = re.search(r"(\d+)\s*(years?|yrs?)", text, re.IGNORECASE)
    sections["Experience (Years)"] = int(experience_match.group(1)) if experience_match else 0

    # Extract CGPA
    cgpa_match = re.search(r"\b\d{1}\.\d{1,2}\b", text)
    sections["CGPA"] = cgpa_match.group(0) if cgpa_match else "Not Found"

    # Extract Location
    location_match = re.search(r"\b(?:Bangalore|Bengaluru|Mumbai|Delhi|Hyderabad|Chennai|Pune|Kolkata|Ahmedabad)\b", text, re.IGNORECASE)
    sections["Location"] = location_match.group(0) if location_match else "Not Found"

    # Extract GitHub Username
    github_username = extract_github_username(text)
    if github_username:
        sections["GitHub Username"] = github_username
        github_analysis = analyze_github(github_username)
        if "projects" in github_analysis:
            sections["Projects"] = github_analysis["projects"]
        if "language_proficiency" in github_analysis:
            sections["Language Proficiency"] = github_analysis["language_proficiency"]

    return sections

# Save Extracted Data to CSV
def save_to_csv(data):
    try:
        with open(csv_filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writerow(data)
    except Exception as e:
        print(f"Error saving data to CSV: {e}")

# Process Resume File
def process_resume(file):
    if not file.name.lower().endswith(".pdf"):
        return {"Error": "Please upload a PDF file."}, "Error: Invalid file type."
    resume_text = extract_text_from_pdf(file.name)
    if not resume_text:
        return {"Error": "Failed to extract text from PDF."}, "Error: Text extraction failed."
    extracted_data = extract_resume_details(resume_text)
    save_to_csv(extracted_data)
    return extracted_data, "Processing complete!"

# GitHub Analyzer Function
def analyze_github(username):
    # Replace with your GitHub token
    token = "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"  # Replace with your token
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # Fetch user data
        user_response = requests.get(f"https://api.github.com/users/{username}", headers=headers)
        if not user_response.ok:
            return {"Error": f"Failed to fetch user data. Status: {user_response.status}"}
        user_data = user_response.json()

        # Fetch repositories
        repos_response = requests.get(user_data["repos_url"], headers=headers)
        if not repos_response.ok:
            return {"Error": f"Failed to fetch repositories. Status: {repos_response.status}"}
        repos_data = repos_response.json()

        # Fetch languages for each repository
        language_summary = {}
        projects = []

        for repo in repos_data:
            languages_response = requests.get(repo["languages_url"], headers=headers)
            if not languages_response.ok:
                continue
            languages_data = languages_response.json()

            # Add project details
            projects.append({
                "name": repo["name"],
                "languages": ", ".join(languages_data.keys()) or "None",
                "description": repo["description"] or "No description",
                "url": repo["html_url"]
            })

            # Update language summary
            for language, bytes in languages_data.items():
                language_summary[language] = language_summary.get(language, 0) + bytes

        # Calculate language proficiency (percentage)
        total_bytes = sum(language_summary.values())
        language_proficiency = {
            lang: (bytes / total_bytes * 100) for lang, bytes in language_summary.items()
        }

        return {
            "projects": projects,
            "language_proficiency": language_proficiency
        }

    except Exception as e:
        return {"Error": str(e)}

# Gradio UI for Resume Extractor and GitHub Analyzer
with gr.Blocks() as demo:
    gr.Markdown("# 📄 Resume Extractor & GitHub Analyzer")
    resume_input = gr.File(label="Upload Resume (PDF)")
    output_text = gr.JSON(label="Extracted Information")
    status = gr.Textbox(label="Status", placeholder="Processing status will appear here.")

    def process_resume_with_status(file):
        extracted_data, status_msg = process_resume(file)
        return extracted_data, status_msg

    process_button = gr.Button("Extract & Analyze")
    process_button.click(
        process_resume_with_status,
        inputs=[resume_input],
        outputs=[output_text, status]
    )

# Launch the app
demo.launch()
