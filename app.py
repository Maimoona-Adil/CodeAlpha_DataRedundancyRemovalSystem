"""
CodeAlpha - Task 1: Data Redundancy Removal System
----------------------------------------------------
A cloud-ready system that:
  1. Classifies incoming data as UNIQUE, EXACT DUPLICATE, or FALSE POSITIVE
     (near-duplicate that looks similar but may not be a real duplicate).
  2. Validates new data against existing records before insertion.
  3. Prevents duplicate data from being added to the database.
  4. Appends only unique / verified entries.
  5. Keeps the database accurate and efficient (indexed lookups, hashing).

Stack: Flask + SQLite (works locally and deploys easily to any cloud
platform such as AWS Elastic Beanstalk, Azure App Service, Render, etc.)
"""

import hashlib
import sqlite3
import difflib
from datetime import datetime
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)
DATABASE = "records.db"

# Similarity threshold: two records above this score (0-1) but not an exact
# match are flagged as "false positive" (likely duplicates needing review).
SIMILARITY_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            data_hash TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'verified',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON records(data_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email ON records(email)")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Core redundancy-detection logic
# ---------------------------------------------------------------------------
def normalize(value: str) -> str:
    """Lowercase + strip whitespace so 'John@Mail.com' == 'john@mail.com'."""
    return (value or "").strip().lower()


def compute_hash(name: str, email: str, phone: str) -> str:
    """Deterministic fingerprint for exact-duplicate detection."""
    raw = f"{normalize(name)}|{normalize(email)}|{normalize(phone)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def classify_entry(name: str, email: str, phone: str):
    """
    Returns a tuple (classification, matched_record_or_None)

    classification is one of:
      - "unique"           -> safe to insert
      - "exact_duplicate"  -> identical record already exists, reject
      - "false_positive"   -> looks similar to an existing record
                               (possible typo/variant), flagged for review
    """
    db = get_db()
    new_hash = compute_hash(name, email, phone)

    # 1) Exact duplicate check (O(1) indexed lookup)
    exact = db.execute(
        "SELECT * FROM records WHERE data_hash = ?", (new_hash,)
    ).fetchone()
    if exact:
        return "exact_duplicate", dict(exact)

    # 2) Near-duplicate / false-positive check against existing records
    #    (fuzzy match on name+email combined string)
    candidates = db.execute("SELECT * FROM records").fetchall()
    new_combined = f"{name} {email}"
    best_score = 0.0
    best_match = None
    for row in candidates:
        existing_combined = f"{row['name']} {row['email']}"
        score = similarity(new_combined, existing_combined)
        if score > best_score:
            best_score = score
            best_match = row

    if best_match and best_score >= SIMILARITY_THRESHOLD:
        return "false_positive", {**dict(best_match), "similarity": round(best_score, 3)}

    return "unique", None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/records", methods=["GET"])
def list_records():
    db = get_db()
    rows = db.execute("SELECT * FROM records ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/check", methods=["POST"])
def check_entry():
    """Validate data WITHOUT inserting it. Used for a 'preview' before submit."""
    payload = request.get_json(force=True) or {}
    name, email, phone = payload.get("name", ""), payload.get("email", ""), payload.get("phone", "")

    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    classification, match = classify_entry(name, email, phone)
    return jsonify({"classification": classification, "match": match})


@app.route("/api/records", methods=["POST"])
def add_record():
    """
    Validate against existing data, then append ONLY unique / verified
    entries. Duplicates are rejected. False positives require force=true
    (i.e. the user/admin manually confirmed it's genuinely a new record).
    """
    payload = request.get_json(force=True) or {}
    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip()
    phone = payload.get("phone", "").strip()
    force = bool(payload.get("force", False))

    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    classification, match = classify_entry(name, email, phone)

    if classification == "exact_duplicate":
        return jsonify({
            "status": "rejected",
            "reason": "exact_duplicate",
            "message": "This entry already exists in the database.",
            "existing_record": match
        }), 409

    if classification == "false_positive" and not force:
        return jsonify({
            "status": "flagged",
            "reason": "false_positive",
            "message": "This entry looks similar to an existing record. "
                        "Resubmit with force=true to confirm it's genuinely unique.",
            "similar_record": match
        }), 409

    db = get_db()
    data_hash = compute_hash(name, email, phone)
    status = "verified" if classification == "unique" else "verified_after_review"
    db.execute(
        "INSERT INTO records (name, email, phone, data_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, email, phone, data_hash, status, datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"status": "inserted", "classification": classification}), 201


@app.route("/api/records/<int:record_id>", methods=["DELETE"])
def delete_record(record_id):
    db = get_db()
    db.execute("DELETE FROM records WHERE id = ?", (record_id,))
    db.commit()
    return jsonify({"status": "deleted"})


@app.route("/api/stats", methods=["GET"])
def stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]
    return jsonify({"total_records": total})


# Initialize the database on import so it works both with `python app.py`
# (local dev) and with a production server like gunicorn (used on Render).
init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
