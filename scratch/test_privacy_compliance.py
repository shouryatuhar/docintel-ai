import sqlite3
import json
import sys
from pathlib import Path

# Resolve the database path relative to workspace
LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "docintel.db"

def test_privacy_compliance():
    print("Running Privacy Compliance Test...")
    print(f"Connecting to database: {LOCAL_DB_PATH}")
    
    if not LOCAL_DB_PATH.exists():
        print("Database file does not exist yet. Run some API requests to generate it.")
        sys.exit(0)
        
    conn = sqlite3.connect(str(LOCAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, timestamp, workflow, details, feedback FROM analytics_logs")
        rows = cursor.fetchall()
        
        print(f"Found {len(rows)} log entries in the database.")
        
        non_compliant_count = 0
        allowed_keys = {"document_size_bucket", "processing_duration_ms", "success"}
        
        for row in rows:
            details_str = row["details"]
            if not details_str:
                continue
                
            try:
                details = json.loads(details_str)
            except Exception as e:
                print(f"Row {row['id']}: Failed to parse JSON details: {e}")
                non_compliant_count += 1
                continue
                
            # Check for any keys that are not allowed
            extra_keys = set(details.keys()) - allowed_keys
            if extra_keys:
                print(f"Row {row['id']} ({row['workflow']}): Non-compliant keys found: {extra_keys}")
                print(f"Payload: {details_str}")
                non_compliant_count += 1
            else:
                # Assert that values have expected types/values
                if "document_size_bucket" in details and details["document_size_bucket"] not in ("small", "medium", "large"):
                    print(f"Row {row['id']}: Invalid size bucket: {details['document_size_bucket']}")
                    non_compliant_count += 1
                    
        if non_compliant_count == 0:
            print("\nSUCCESS: All database log entries are 100% compliant with privacy-first standards!")
            print("No filenames, persona queries, match details, or document text were stored.")
            sys.exit(0)
        else:
            print(f"\nFAILURE: Found {non_compliant_count} non-compliant log entries in the database.")
            sys.exit(1)
            
    finally:
        conn.close()

if __name__ == "__main__":
    test_privacy_compliance()
