
from flask import Flask, render_template, request
from pypdf import PdfReader
import re
import io

app = Flask(__name__)

SKILLS = [
    "python", "java", "javascript", "html", "css",
    "flask", "django", "react", "angular", "sql",
    "mysql", "mongodb", "machine learning", "deep learning",
    "artificial intelligence", "data analysis", "pandas",
    "numpy", "scikit-learn", "git", "github", "rest api",
    "communication", "problem solving", "excel",
    "power bi", "tensorflow", "pytorch", "aws"
]

# Equivalent names for the same skill
SKILL_ALIASES = {
    "html": ["html5"],
    "css": ["css3"],
    "javascript": ["js"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "rest api": ["rest apis", "restful api", "restful apis"],
    "problem solving": ["problem-solving"]
}


def extract_pdf_text(file):
    reader = PdfReader(io.BytesIO(file.read()))
    return " ".join(page.extract_text() or "" for page in reader.pages)


def contains_skill(text, skill):
    """Check whether a skill or one of its accepted aliases occurs."""
    names = [skill] + SKILL_ALIASES.get(skill, [])

    for name in names:
        pattern = r"(?<!\w)" + re.escape(name) + r"(?!\w)"
        if re.search(pattern, text):
            return True

    return False


def extract_skills(text):
    text = text.lower()
    found = []

    for skill in SKILLS:
        if contains_skill(text, skill):
            found.append(skill)

    return found


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    if request.method == "POST":
        resume = request.files.get("resume")
        job_description = request.form.get(
            "job_description", ""
        ).strip()

        if not resume or not resume.filename:
            error = "Please upload your resume PDF."

        elif not resume.filename.lower().endswith(".pdf"):
            error = "Please upload a PDF file."

        elif not job_description:
            error = "Please enter the job description."

        else:
            try:
                resume_text = extract_pdf_text(resume)

                if not resume_text.strip():
                    error = (
                        "No readable text found. "
                        "Please try a text-based PDF."
                    )

                else:
                    resume_skills = extract_skills(resume_text)
                    required_skills = extract_skills(job_description)

                    matched = [
                        skill for skill in required_skills
                        if contains_skill(resume_text.lower(), skill)
                    ]

                    missing = [
                        skill for skill in required_skills
                        if skill not in matched
                    ]

                    score = (
                        round(len(matched) / len(required_skills) * 100)
                        if required_skills else 0
                    )

                    result = {
                        "score": score,
                        "matched": matched,
                        "missing": missing,
                        "resume_skills": resume_skills,
                        "total_required": len(required_skills)
                    }

            except Exception:
                error = (
                    "Unable to read this PDF. "
                    "Please try another file."
                )

    return render_template(
        "index.html",
        result=result,
        error=error
    )


if __name__ == "__main__":
    app.run(debug=True)

