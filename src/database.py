"""Analytics database layer supporting Upstash Redis REST API and local SQLite fallback."""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Check environment for Redis connection
KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")

# Local SQLite Database Path
LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "docintel.db"


def _is_redis_enabled() -> bool:
    """Check if production Redis is configured via environment variables."""
    return bool(KV_URL and KV_TOKEN)


def _execute_redis_cmd(cmd: list[Any]) -> Any:
    """Execute a Redis command via the Upstash HTTPS REST API."""
    if not KV_URL or not KV_TOKEN:
        return None

    # Upstash REST API expects JSON list representing command and arguments
    payload = json.dumps(cmd).encode("utf-8")
    req = urllib.request.Request(
        KV_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {KV_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            res_json = json.loads(res_data)
            if "error" in res_json:
                raise RuntimeError(f"Redis REST error: {res_json['error']}")
            return res_json.get("result")
    except urllib.error.URLError as e:
        print(f"Failed to connect to Redis REST API: {e}")
        raise RuntimeError(f"Redis connection failed: {e}") from e
    except Exception as e:
        print(f"Error executing Redis command {cmd[0]}: {e}")
        raise


def _get_sqlite_conn() -> sqlite3.Connection:
    """Open a connection to the local SQLite database, creating parent directories if needed."""
    db_path = LOCAL_DB_PATH
    try:
        # Check if the folder is writable. If not (e.g. on Vercel), fallback to /tmp
        if not os.access(db_path.parent, os.W_OK):
            db_path = Path("/tmp/docintel.db")
    except Exception:
        db_path = Path("/tmp/docintel.db")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database tables for local SQLite fallback. No-op for Redis."""
    if _is_redis_enabled():
        # Redis creates keys dynamically, no schema creation needed
        return

    conn = _get_sqlite_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                workflow TEXT,
                details TEXT,
                feedback INTEGER
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_size_bucket(size_bytes: int) -> str:
    """Classify file size in bytes to a generic category bucket."""
    if size_bytes < 512000:
        return "small"
    elif size_bytes < 2048000:
        return "medium"
    return "large"


def log_event(workflow: str, size_bytes: int, duration_ms: int, success: bool) -> int:
    """Log an anonymous analysis event to the active database and increment metrics."""
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp_str = datetime.now(timezone.utc).isoformat()
    bucket = get_size_bucket(size_bytes)
    
    details = {
        "document_size_bucket": bucket,
        "processing_duration_ms": duration_ms,
        "success": success
    }

    if _is_redis_enabled():
        try:
            # 1. Get next sequence ID
            event_id = _execute_redis_cmd(["INCR", "docintel:logs:next_id"])
            
            # 2. Build log record
            log_record = {
                "id": event_id,
                "timestamp": timestamp_str,
                "workflow": workflow,
                "details": details,
                "feedback": None
            }
            
            # 3. Save to log hash map
            _execute_redis_cmd(["HSET", "docintel:logs", str(event_id), json.dumps(log_record)])
            
            # 4. Increment aggregate metrics
            _execute_redis_cmd(["INCR", "docintel:metrics:documents_analyzed"])
            if workflow == "resume-fit":
                _execute_redis_cmd(["INCR", "docintel:metrics:resume_checks"])
            
            # Increment daily counts and workflow breakdown
            _execute_redis_cmd(["HINCRBY", "docintel:metrics:workflows", workflow, 1])
            _execute_redis_cmd(["HINCRBY", "docintel:metrics:daily_usage", today_date, 1])
            
            return int(event_id)
        except Exception as e:
            print(f"Redis log_event failed: {e}")
            # Non-blocking log failure
            return 1
    else:
        conn = _get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO analytics_logs (workflow, details) VALUES (?, ?)",
                (workflow, json.dumps(details))
            )
            event_id = cursor.lastrowid or 1
            conn.commit()
            return event_id
        finally:
            conn.close()


def log_feedback(event_id: int, is_useful: bool) -> bool:
    """Save user thumbs up/down feedback to the active database (Redis or SQLite)."""
    feedback_value = 1 if is_useful else -1

    if _is_redis_enabled():
        try:
            # 1. Retrieve log record
            log_str = _execute_redis_cmd(["HGET", "docintel:logs", str(event_id)])
            if not log_str:
                return False
            
            log_record = json.loads(log_str)
            log_record["feedback"] = feedback_value
            
            # 2. Update record in hash map
            _execute_redis_cmd(["HSET", "docintel:logs", str(event_id), json.dumps(log_record)])
            
            # 3. Update feedback counters
            if is_useful:
                _execute_redis_cmd(["INCR", "docintel:metrics:thumbs_up"])
            else:
                _execute_redis_cmd(["INCR", "docintel:metrics:thumbs_down"])
            return True
        except Exception as e:
            print(f"Redis log_feedback failed: {e}")
            return False
    else:
        conn = _get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE analytics_logs SET feedback = ? WHERE id = ?",
                (feedback_value, event_id)
            )
            updated = cursor.rowcount > 0
            conn.commit()
            return updated
        finally:
            conn.close()


def get_metrics() -> dict[str, Any]:
    """Retrieve raw aggregated metrics from the database. No base offsets applied."""
    if _is_redis_enabled():
        try:
            # Fetch raw counters
            docs_analyzed_raw = _execute_redis_cmd(["GET", "docintel:metrics:documents_analyzed"])
            resume_checks_raw = _execute_redis_cmd(["GET", "docintel:metrics:resume_checks"])
            thumbs_up_raw = _execute_redis_cmd(["GET", "docintel:metrics:thumbs_up"])
            
            documents_analyzed = int(docs_analyzed_raw) if docs_analyzed_raw else 0
            resume_checks = int(resume_checks_raw) if resume_checks_raw else 0
            thumbs_up = int(thumbs_up_raw) if thumbs_up_raw else 0
            
            # Fetch hashes
            workflows_raw = _execute_redis_cmd(["HGETALL", "docintel:metrics:workflows"]) or []
            daily_usage_raw = _execute_redis_cmd(["HGETALL", "docintel:metrics:daily_usage"]) or []
            
            # Convert alternating key-value lists to dictionaries
            workflows = {}
            if workflows_raw:
                # Upstash HGETALL returns list/dict based on formatting, usually a list of strings
                if isinstance(workflows_raw, list):
                    for i in range(0, len(workflows_raw), 2):
                        workflows[workflows_raw[i]] = int(workflows_raw[i+1])
                elif isinstance(workflows_raw, dict):
                    workflows = {k: int(v) for k, v in workflows_raw.items()}

            daily_usage = []
            if daily_usage_raw:
                usage_dict = {}
                if isinstance(daily_usage_raw, list):
                    for i in range(0, len(daily_usage_raw), 2):
                        usage_dict[daily_usage_raw[i]] = int(daily_usage_raw[i+1])
                elif isinstance(daily_usage_raw, dict):
                    usage_dict = {k: int(v) for k, v in daily_usage_raw.items()}
                
                # Sort dates
                sorted_days = sorted(usage_dict.keys())
                for day in sorted_days:
                    daily_usage.append({"date": day, "count": usage_dict[day]})
            
            # Calculate users helped (real data only)
            users_helped = documents_analyzed + thumbs_up

            return {
                "documents_analyzed": documents_analyzed,
                "resume_checks": resume_checks,
                "users_helped": users_helped,
                "daily_usage": daily_usage,
                "workflows": workflows
            }
        except Exception as e:
            print(f"Redis get_metrics failed: {e}")
            return {
                "documents_analyzed": 0,
                "resume_checks": 0,
                "users_helped": 0,
                "daily_usage": [],
                "workflows": {}
            }
    else:
        conn = _get_sqlite_conn()
        try:
            cursor = conn.cursor()
            
            # 1. Total documents processed
            cursor.execute("SELECT COUNT(*) FROM analytics_logs")
            documents_analyzed = cursor.fetchone()[0] or 0
            
            # 2. Resume checks completed
            cursor.execute("SELECT COUNT(*) FROM analytics_logs WHERE workflow = 'resume-fit'")
            resume_checks = cursor.fetchone()[0] or 0
            
            # 3. Users helped (real documents + positive feedbacks)
            cursor.execute("SELECT COUNT(*) FROM analytics_logs WHERE feedback = 1")
            positive_feedback = cursor.fetchone()[0] or 0
            users_helped = documents_analyzed + positive_feedback
            
            # 4. Daily usage
            cursor.execute("""
                SELECT date(timestamp) as day, COUNT(*) as count 
                FROM analytics_logs 
                GROUP BY day 
                ORDER BY day ASC
                LIMIT 30
            """)
            daily_usage = [{"date": r["day"], "count": r["count"]} for r in cursor.fetchall()]
            
            # 5. Workflow breakdown
            cursor.execute("""
                SELECT workflow, COUNT(*) as count 
                FROM analytics_logs 
                GROUP BY workflow
            """)
            workflows = {r["workflow"]: r["count"] for r in cursor.fetchall()}
            
            return {
                "documents_analyzed": documents_analyzed,
                "resume_checks": resume_checks,
                "users_helped": users_helped,
                "daily_usage": daily_usage,
                "workflows": workflows
            }
        finally:
            conn.close()
