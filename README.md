# CodeAlpha_DataRedundancyRemovalSystem

**Task 1 — Data Redundancy Removal System**
Cloud Computing Internship, CodeAlpha

A web app that validates new data against an existing database before
storing it — preventing duplicates while flagging "false positive"
near-duplicates (e.g. typos) for manual review instead of silently
rejecting or silently inserting them.

## How it satisfies the task

| Requirement | Implementation |
|---|---|
| Classify data as redundant or false positive | `classify_entry()` returns `unique`, `exact_duplicate`, or `false_positive` |
| Validate new data against existing data | SHA-256 fingerprint check (exact) + fuzzy string similarity check (near-duplicate) before every insert |
| Prevent duplicate data from being added | Exact duplicates are rejected outright (HTTP 409) |
| Append only unique/verified entries | Only `unique` or manually-confirmed (`force=true`) entries are written to the DB |
| Accuracy & efficiency | Indexed hash + email lookups in SQLite; classification runs in a single pass |

## Stack

- **Backend:** Python, Flask
- **Database:** SQLite (swap the connection string for MySQL/Postgres to run on AWS RDS, Azure SQL, etc. — the rest of the code is unchanged)
- **Frontend:** Vanilla HTML/CSS/JS (no build step)

## How it works

1. A new entry (`name`, `email`, `phone`) is submitted.
2. The server computes a SHA-256 hash of the normalized fields and checks it
   against every stored hash — an exact match means it's a real duplicate
   and is **rejected**.
3. If no exact match is found, the server runs a fuzzy similarity check
   (`difflib.SequenceMatcher`) against existing records. A high similarity
   score (≥ 85%) but non-identical data is classified as a **false
   positive** — likely the same person with a typo, or a coincidental
   near-match — and is flagged for manual confirmation rather than
   auto-inserted or auto-rejected.
4. Only entries classified as `unique`, or `false_positive` entries the
   user explicitly confirms, are appended to the database.

## Run it locally

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000` in your browser.

## API reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/records` | List all stored records |
| `POST` | `/api/check` | Preview classification without inserting |
| `POST` | `/api/records` | Validate + insert (rejects duplicates, flags false positives) |
| `DELETE` | `/api/records/<id>` | Remove a record |
| `GET` | `/api/stats` | Total record count |

## Deploying to the cloud

This app runs unmodified on any platform that supports Python/Flask:

- **Render / Railway:** connect the repo, set start command to `python app.py`
- **AWS Elastic Beanstalk:** `eb init` + `eb create` (Flask is auto-detected)
- **Azure App Service:** deploy via `az webapp up`

For production, replace SQLite with a managed database (RDS, Azure SQL,
Cloud SQL) by swapping the `sqlite3.connect(...)` call for the appropriate
driver — the validation logic itself is database-agnostic.

## Project structure

```
CodeAlpha_DataRedundancyRemovalSystem/
├── app.py              # Flask backend + redundancy detection logic
├── templates/
│   └── index.html      # UI
├── static/
│   └── style.css
├── requirements.txt
└── README.md
```

---
*Built for the CodeAlpha Cloud Computing Internship.*
