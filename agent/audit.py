"""
audit.py

Logs every reasoning step (node name, SQL run, summary) to a local
SQLite audit table.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = "db/audit.sqlite"


def init_audit_db():
    os.makedirs("db", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            question TEXT,
            node_name TEXT,
            sql_text TEXT,
            summary TEXT
        )
    """)
    con.commit()
    con.close()


def log_step(question: str, node_name: str, sql_text: str = "", summary: str = ""):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO audit_log (timestamp, question, node_name, sql_text, summary) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), question, node_name, sql_text, summary),
    )
    con.commit()
    con.close()