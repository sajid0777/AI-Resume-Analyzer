import io
import os
import re
import sqlite3
from functools import wraps
from collections import defaultdict

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "resume_analyzer.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

# Skills are grouped so related aliases are counted once.
SKILL_GROUPS = {
    "python": ["python", "python3"],
    "java": ["java", "core java"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "html": ["html", "html5"],
    "css": ["css", "css3", "cascading style sheets"],
    "flask": ["flask"],
    "django": ["django"],
    "react": ["react", "reactjs", "react.js"],
    "angular": ["angular", "angularjs"],
    "node.js": ["node.js", "nodejs", "node js"],
    "express.js": ["express.js", "expressjs", "express js"],
    "sql": ["sql", "structured query language"],
    "mysql": ["mysql", "my sql"],
    "postgresql": ["postgresql", "postgres"],
    "sqlite": ["sqlite", "sqlite3"],
    "mongodb": ["mongodb", "mongo db"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "artificial intelligence": ["artificial intelligence", "ai"],
    "data analysis": ["data analysis", "data analytics"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "git": ["git"],
    "github": ["github", "git hub"],
    "rest api": ["rest api", "rest apis", "restful api", "restful apis", "rest api development"],
    "communication": ["communication", "verbal communication", "written communication"],
    "problem solving": ["problem solving", "problem-solving", "analytical thinking"],
    "excel": ["excel", "microsoft excel"],
    "power bi": ["power bi", "powerbi"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "linux": ["linux"],
    "oop": ["object-oriented programming", "object oriented programming", "oop"],
    "data structures": ["data structures", "data structure"],
    "algorithms": ["algorithms", "algorithm design"],
    "api testing": ["api testing"],
    "testing": ["software testing", "unit testing", "testing"],
    "agile": ["agile", "scrum"],
    "powerpoint": ["powerpoint", "power point"],
}

REQUIRED_HINTS = ("must have", "required", "requirements", "essential", "mandatory", "you will need")
PREFERRED_HINTS = ("preferred", "nice to have", "bonus", "desirable", "plus", "ideally")


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(os.path.abspath(DATABASE)), exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            phone TEXT DEFAULT '',
            location TEXT DEFAULT '',
            education TEXT DEFAULT '',
            preferred_role TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL DEFAULT 'Resume analysis',
            job_description TEXT NOT NULL,
            score INTEGER NOT NULL,
            matched_skills TEXT NOT NULL,
            missing_skills TEXT NOT NULL,
            resume_skills TEXT NOT NULL,
            suggestions TEXT NOT NULL,
            prompt TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    db.commit()


with app.app_context():
    init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access that page.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    user = None
    if session.get("user_id"):
        user = get_db().execute(
            "SELECT id, full_name, email FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()
    return {"current_user": user}


def extract_pdf_text(file_storage):
    reader = PdfReader(io.BytesIO(file_storage.read()))
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:
            return ""
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _pattern_for(term):
    # Flexible punctuation lets React.js and React JS variants match.
    escaped = re.escape(term.strip())
    escaped = escaped.replace(r"\ ", r"[\s\-_]*")
    escaped = escaped.replace(r"\.", r"\.?")
    return r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])"


def contains_term(text, term):
    return bool(re.search(_pattern_for(term.lower()), text.lower()))


def extract_skills(text):
    lowered = text.lower()
    found = []
    for canonical, aliases in SKILL_GROUPS.items():
        if any(contains_term(lowered, alias) for alias in aliases):
            found.append(canonical)
    return found


def classify_requirements(job_description, skills):
    """Basic heuristic classification; labels are estimates, not NLP certainty."""
    lines = [line.strip(" \t•-*") for line in job_description.splitlines() if line.strip()]
    required, preferred = [], []
    for skill in skills:
        found_lines = [line.lower() for line in lines if any(contains_term(line, a) for a in SKILL_GROUPS[skill])]
        joined = " ".join(found_lines)
        if any(hint in joined for hint in PREFERRED_HINTS):
            preferred.append(skill)
        else:
            required.append(skill)
    return required, preferred


def make_improvement_suggestions(resume_text, job_description, matched, missing):
    suggestions = []
    resume_lower = resume_text.lower()
    if not any(term in resume_lower for term in ["project", "projects"]):
        suggestions.append("Consider adding a Projects section with 1–3 relevant projects and your specific contribution.")
    if not any(term in resume_lower for term in ["education", "bachelor", "b.tech", "degree", "diploma"]):
        suggestions.append("Check whether your education and relevant qualifications are clearly listed.")
    if not any(term in resume_lower for term in ["experience", "internship", "employment"]):
        suggestions.append("If applicable, add internship, work, volunteering, or practical experience relevant to the role.")
    if missing:
        suggestions.append("Review the requirements not detected below. Add a skill only if you genuinely have it, and support it with evidence where possible.")
    if matched:
        suggestions.append("Make your matched skills easier to verify by showing where you used them in projects, coursework, or work experience.")
    if not any(term in resume_lower for term in ["%", "increased", "reduced", "improved", "built", "developed", "implemented"]):
        suggestions.append("Where truthful, strengthen project bullets with concrete outcomes, scope, or measurable results.")
    if not suggestions:
        suggestions.append("Review each section for clarity, consistency, and evidence that supports the target role.")
    return suggestions[:6]


def build_prompt(job_description, matched, missing, suggestions):
    """Build a detailed, job-specific prompt for truthful resume tailoring."""
    matched_text = ", ".join(matched) if matched else "No listed skills detected as matches"
    missing_text = ", ".join(missing) if missing else "No listed skill gaps detected"
    suggestion_text = "\n".join(f"- {item}" for item in suggestions) or "- No additional suggestions generated"

    return f"""Act as a senior technical recruiter, ATS resume optimization specialist,
and professional resume writer.

YOUR MISSION
Create a complete, targeted, ATS-friendly version of my existing resume for the
specific job description below. Do not merely provide generic advice: produce
actual revised resume content that I can verify and use.

NON-NEGOTIABLE ACCURACY RULES
- Never invent employment, internships, projects, qualifications, certifications,
  dates, achievements, metrics, responsibilities, or technical experience.
- A skill missing from the resume is not necessarily a skill I lack; however, do
  not claim I possess it unless my resume or my confirmation supports that claim.
- Separate demonstrated skills from unverified skills and genuine learning gaps.
- You may recommend edits or project enhancements, but label uncompleted work as
  a recommendation. Do not put it in the final resume as completed experience.
- Do not insert missing keywords solely to manipulate ATS screening.
- Preserve my real education, identity, dates, and experience.

STEP 1 — ANALYZE THE JOB DESCRIPTION
Identify and prioritize:
- Required and preferred technical skills, languages, frameworks, databases, and tools.
- Core responsibilities and role-specific keywords.
- Required qualifications and relevant soft skills.
Distinguish essential requirements from preferred skills when the description allows it.

STEP 2 — COMPARE THE RESUME WITH THE ROLE
The analyzer findings below are keyword-based clues, not proof of proficiency.

Skills detected as matches:
{matched_text}

Job-description skills not detected in the resume:
{missing_text}

Additional improvement suggestions:
{suggestion_text}

Classify each important requirement as:
A. Demonstrated in the existing resume.
B. Possibly possessed but not sufficiently explained; ask me to confirm if needed.
C. Not demonstrated and requiring learning, practice, or project evidence.

STEP 3 — TAILOR THE RESUME SECTION BY SECTION

A. PROFESSIONAL SUMMARY
Write a concise, specific summary for this exact job. Lead with relevant skills and
projects that are actually supported by the resume. Avoid generic claims and
unsupported statements about experience or expertise.

B. TECHNICAL SKILLS
Reorder the existing skills to prioritize the job requirements. Include relevant
skills already demonstrated or explicitly confirmed. Put unverified/missing skills
in a separate confirmation list; do not present them as existing competencies.

C. PROJECTS
Rewrite relevant existing project descriptions to highlight the technologies,
implementation details, problem-solving, and contributions supported by my resume.
Use clear action verbs and specific technical detail, without inventing results.
For each important missing skill that could be demonstrated through a project,
recommend a concrete enhancement and explain:
- What feature or task to implement.
- Which job requirement it demonstrates.
- What evidence I should be able to show after completing it.
- A suggested resume bullet that I may use ONLY after genuinely completing the work.

D. EXPERIENCE AND EDUCATION
Improve clarity, relevance, and formatting without changing factual details. Do not
invent professional experience, internships, responsibilities, or qualifications.

E. OTHER SECTIONS
Recommend relevant coursework, certifications, or achievements only when supported
by my information, or clearly label them as future actions.

STEP 4 — ADDRESS MISSING SKILLS DIRECTLY
Create a prioritized table with these columns:
1. Missing or unverified skill.
2. Importance to the target role.
3. Evidence currently present in the resume, if any.
4. Specific action to learn or demonstrate the skill.
5. Suggested resume bullet to use after genuinely completing that action.

Do not simply add missing skills to the resume. Show me how to acquire or prove them.
If a skill is already possessed but omitted, tell me to confirm it and then show where
it can truthfully be added.

STEP 5 — ATS OPTIMIZATION
- Use conventional headings and a clean, ATS-readable layout.
- Include relevant job-description keywords naturally and in context.
- Use concise, action-oriented bullet points and consistent formatting.
- Avoid keyword stuffing, fabricated achievements, tables in the final resume when a
  simpler layout is more ATS-compatible, and claims of a guaranteed ATS score.

REQUIRED OUTPUT — RETURN IN THIS ORDER
1. JOB REQUIREMENTS: prioritized essential and preferred skills.
2. MATCHED SKILLS: skills supported by my current resume.
3. MISSING / UNVERIFIED SKILLS: clearly categorized and prioritized.
4. COMPLETE TAILORED RESUME: provide the entire revised resume, not just advice.
5. SKILL-GAP ACTION PLAN: concrete learning tasks and project enhancements.
6. FINAL VERIFICATION CHECKLIST: claims I must confirm before using the resume.

The complete resume should be ready to copy into a document after I verify it.
Keep uncompleted work and unverified skills OUT of the final resume and list them
separately as recommendations. If the resume text is not included below, ask me to
paste or upload it rather than inventing its contents.

TARGET JOB DESCRIPTION:
{job_description}

EXISTING RESUME:
I will provide my current resume text or upload the original resume. If the AI tool
receiving this prompt cannot access an uploaded file, ask me to paste the resume text.

Your priority is a genuinely tailored resume that highlights existing strengths and
gives me a practical path to close missing-skill gaps truthfully."""


def analyze_resume(resume_text, job_description):
    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_description)
    required, preferred = classify_requirements(job_description, job_skills)

    matched_required = [skill for skill in required if skill in resume_skills]
    missing_required = [skill for skill in required if skill not in resume_skills]
    matched_preferred = [skill for skill in preferred if skill in resume_skills]
    missing_preferred = [skill for skill in preferred if skill not in resume_skills]

    # Required skills weigh 2; preferred skills weigh 1. If no required skills
    # are detected, use preferred skills equally. Score is explicitly not ATS.
    denominator = (2 * len(required)) + len(preferred)
    numerator = (2 * len(matched_required)) + len(matched_preferred)
    score = round(numerator / denominator * 100) if denominator else 0

    matched = matched_required + matched_preferred
    missing = missing_required + missing_preferred
    suggestions = make_improvement_suggestions(resume_text, job_description, matched, missing)
    prompt = build_prompt(job_description, matched, missing, suggestions)

    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "resume_skills": resume_skills,
        "required": required,
        "preferred": preferred,
        "matched_required": matched_required,
        "missing_required": missing_required,
        "matched_preferred": matched_preferred,
        "missing_preferred": missing_preferred,
        "suggestions": suggestions,
        "prompt": prompt,
        "total_required": len(required),
        "total_preferred": len(preferred),
    }


@app.route("/")
def home():
    return render_template("landing.html")


@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    result, error = None, None
    if request.method == "POST":
        resume = request.files.get("resume")
        job_description = request.form.get("job_description", "").strip()
        title = request.form.get("title", "").strip()[:100] or "Resume analysis"

        if not resume or not resume.filename:
            error = "Please choose a resume PDF."
        elif not resume.filename.lower().endswith(".pdf"):
            error = "Please upload a PDF file."
        elif not job_description:
            error = "Please paste the job description."
        else:
            try:
                resume_text = extract_pdf_text(resume)
                if not resume_text.strip():
                    error = "No readable text was found. Try a text-based PDF rather than a scanned image."
                else:
                    result = analyze_resume(resume_text, job_description)
                    result["title"] = title
                    if session.get("user_id"):
                        db = get_db()
                        db.execute("""INSERT INTO analyses
                            (user_id, title, job_description, score, matched_skills,
                             missing_skills, resume_skills, suggestions, prompt)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (session["user_id"], title, job_description, result["score"],
                             "\n".join(result["matched"]), "\n".join(result["missing"]),
                             "\n".join(result["resume_skills"]), "\n".join(result["suggestions"]),
                             result["prompt"]))
                        db.commit()
                    else:
                        flash("Guest analysis is not saved. Create a free account to keep your history.", "info")
            except Exception:
                app.logger.exception("Resume analysis failed")
                error = "We couldn't read this PDF. Please try another text-based PDF."
    return render_template("analyze.html", result=result, error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or not email or not password:
            flash("Please complete all required fields.", "error")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            try:
                db = get_db()
                cursor = db.execute(
                    "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                    (name[:100], email, generate_password_hash(password))
                )
                db.commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                flash("Your account has been created.", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    count = db.execute("SELECT COUNT(*) AS n FROM analyses WHERE user_id = ?", (user_id,)).fetchone()["n"]
    recent = db.execute("SELECT id, title, score, created_at FROM analyses WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,)).fetchall()
    return render_template("dashboard.html", count=count, recent=recent)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        education = request.form.get("education", "").strip()
        preferred_role = request.form.get("preferred_role", "").strip()
        if not name or not email:
            flash("Name and email are required.", "error")
        else:
            try:
                db.execute("""UPDATE users SET full_name=?, email=?, phone=?, location=?,
                    education=?, preferred_role=? WHERE id=?""",
                    (name[:100], email, phone[:40], location[:100], education[:200], preferred_role[:100], session["user_id"]))
                db.commit()
                flash("Profile updated.", "success")
                return redirect(url_for("profile"))
            except sqlite3.IntegrityError:
                flash("That email is already used by another account.", "error")
        user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return render_template("profile.html", user=user)


@app.route("/history")
@login_required
def history():
    rows = get_db().execute(
        "SELECT id, title, score, created_at FROM analyses WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    return render_template("history.html", analyses=rows)


@app.route("/history/<int:analysis_id>")
@login_required
def analysis_detail(analysis_id):
    row = get_db().execute(
        "SELECT * FROM analyses WHERE id = ? AND user_id = ?",
        (analysis_id, session["user_id"])
    ).fetchone()
    if not row:
        flash("Analysis not found.", "error")
        return redirect(url_for("history"))
    result = {
        "score": row["score"],
        "matched": row["matched_skills"].splitlines() if row["matched_skills"] else [],
        "missing": row["missing_skills"].splitlines() if row["missing_skills"] else [],
        "resume_skills": row["resume_skills"].splitlines() if row["resume_skills"] else [],
        "suggestions": row["suggestions"].splitlines() if row["suggestions"] else [],
        "prompt": row["prompt"],
        "title": row["title"],
        "saved": True,
    }
    return render_template("history_detail.html", result=result, analysis=row)


@app.route("/history/<int:analysis_id>/delete", methods=["POST"])
@login_required
def delete_analysis(analysis_id):
    db = get_db()
    db.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, session["user_id"]))
    db.commit()
    flash("Analysis deleted if it belonged to your account.", "info")
    return redirect(url_for("history"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        user = get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not check_password_hash(user["password_hash"], current):
            flash("Current password is incorrect.", "error")
        elif len(new) < 8:
            flash("New password must contain at least 8 characters.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        else:
            get_db().execute("UPDATE users SET password_hash = ? WHERE id = ?",
                             (generate_password_hash(new), session["user_id"]))
            get_db().commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("settings"))
    return render_template("settings.html")
@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not user:
        session.clear()
        flash("Account not found.", "error")
        return redirect(url_for("home"))

    if not check_password_hash(user["password_hash"], password):
        flash("Incorrect password.", "error")
        return redirect(url_for("settings"))

    try:
        db.execute(
            "DELETE FROM users WHERE id = ?",
            (session["user_id"],)
        )
        db.commit()

        session.clear()
        flash("Your account and analysis history have been deleted.", "success")
        return redirect(url_for("home"))

    except sqlite3.Error:
        db.rollback()
        app.logger.exception("Account deletion failed")
        flash("Account deletion failed. Please try again.", "error")
        return redirect(url_for("settings"))@app.errorhandler(413)
def too_large(_error):
    flash("That file is too large. Please upload a PDF under 5 MB.", "error")
    return redirect(url_for("analyze"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
