# VioletCV — AI Resume Analyzer 2.0

A Flask resume-to-job-description comparison tool with a purple/black SaaS UI, secure account login, editable profiles, saved analysis history, and copy-ready improvement prompts.

## Features
- Guest resume analysis without creating an account
- Registration/login using Werkzeug password hashing
- Editable account profile and password change
- PDF text extraction (text-based PDFs; scanned PDFs may not work)
- Skill normalization and aliases (e.g. React/ReactJS, HTML/HTML5)
- Simple rule-based required/preferred weighting where job-description wording allows
- Match score explanation, matched skills, and skills not detected
- Personalized suggestions and a copyable prompt for use with any AI assistant
- Per-user analysis history and deletion
- Responsive dark-purple UI

## Important limitations
The percentage is a rule-based resume–job-description match estimate, **not an ATS score**. It does not reproduce any specific applicant tracking system and does not predict hiring outcomes. The analyzer uses a predefined skill dictionary and heuristic classification; it can miss synonyms, context, and skills not listed. A missing term is not proof that a person lacks that skill.

No paid AI API is used. The prompt is generated locally from the analysis results.

## Run locally
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

python -m pip install -r requirements.txt
```

Set a secret key before deploying (PowerShell):
```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
python app.py
```

Then open `http://127.0.0.1:5000`.

## Deployment notes
- Configure `SECRET_KEY` as a long random secret in your hosting provider.
- Set `DATABASE_PATH` to a location on a persistent disk, or use a managed persistent database. Render's ephemeral filesystem can lose SQLite data on redeploy/restart.
- The uploaded PDF is processed in memory and isn't saved as a file. Saved analyses include job description and generated results, so treat the database as personal data.
- Add HTTPS, rate limiting, email verification, CSRF protection, and a proper managed database before using this for sensitive or production workloads.
- Debug mode is off by default.

## Project structure
- `app.py` — Flask routes, database, matching engine, authentication
- `templates/` — pages
- `static/style.css` — theme and responsive styles
