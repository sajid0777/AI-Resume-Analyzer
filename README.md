@"
# AI Resume Analyzer

A Flask-based web application that compares resume skills with job descriptions.

## Features
- Upload PDF resumes
- Extract text from PDF files
- Identify matching and missing skills
- Calculate a skill-match percentage
- Responsive web interface

## Technologies
- Python
- Flask
- PyPDF
- HTML
- CSS

## Run locally
Install dependencies:

    python -m pip install -r requirements.txt

Start the application:

    python app.py

Open http://127.0.0.1:5000 in your browser.

## Limitations
The match percentage is based on a predefined list of skills. It is not an AI model or a comprehensive assessment of a candidate's qualifications.
