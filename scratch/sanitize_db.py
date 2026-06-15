import sqlite3
import json
from pathlib import Path

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "docintel.db"

def sanitize_db():
    print(f"Sanitizing database logs at {LOCAL_DB_PATH}...")
    if not LOCAL_DB_PATH.exists():
        print("Database does not exist.")
        return

    conn = sqlite3.connect(str(LOCAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, workflow, details FROM analytics_logs")
        rows = cursor.fetchall()
        
        allowed_keys = {"document_size_bucket", "processing_duration_ms", "success"}
        updated_count = 0

        for row in rows:
            details_str = row["details"]
            if not details_str:
                new_details = {
                    "document_size_bucket": "small",
                    "processing_duration_ms": 0,
                    "success": True
                }
                cursor.execute(
                    "UPDATE analytics_logs SET details = ? WHERE id = ?",
                    (json.dumps(new_details), row["id"])
                )
                updated_count += 1
                continue

            try:
                details = json.loads(details_str)
            except Exception:
                details = {}

            # Check if it contains non-compliant keys
            extra_keys = set(details.keys()) - allowed_keys
            if extra_keys:
                # Sanitize the details
                new_details = {
                    "document_size_bucket": details.get("document_size_bucket", "small"),
                    "processing_duration_ms": details.get("processing_duration_ms", 0),
                    "success": details.get("success", True)
                }
                cursor.execute(
                    "UPDATE analytics_logs SET details = ? WHERE id = ?",
                    (json.dumps(new_details), row["id"])
                )
                updated_count += 1

        conn.commit()
        print(f"Successfully sanitized {updated_count} historical database log entries.")
        
    finally:
        conn.close()

if __name__ == "__main__":
    sanitize_db()
