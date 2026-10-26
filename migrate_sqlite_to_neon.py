"""Copy Student Study Planner SQLite data to an empty Neon PostgreSQL database.

Usage:
  export DATABASE_URL='your Neon connection string'
  python migrate_sqlite_to_neon.py /path/to/database.db

The source SQLite file is opened read-only and never changed. The script refuses
non-empty destination tables to avoid accidental duplicate imports.
"""
import os, sqlite3, sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

TABLES = {
    "users": ["id", "name", "email", "password_hash"],
    "tasks": ["id", "subject", "topic", "study_date", "study_time", "priority", "status", "user_id"],
    "notes": ["id", "title", "subject", "content", "important", "created_at", "user_id"],
    "goals": ["id", "title", "target_date", "progress", "status", "user_id"],
    "reminders": ["id", "title", "reminder_date", "reminder_time", "status", "user_id"],
    "study_sessions": ["id", "subject", "duration", "session_date", "user_id"],
    "timetable": ["id", "entry_type", "day", "title", "start_time", "end_time", "location", "teacher", "notes", "user_id"],
}
SCHEMA = [
"""CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS tasks (id BIGSERIAL PRIMARY KEY, subject TEXT NOT NULL, topic TEXT NOT NULL, study_date TEXT NOT NULL, study_time TEXT, priority TEXT DEFAULT 'Medium', status TEXT DEFAULT 'Pending', user_id BIGINT)""",
"""CREATE TABLE IF NOT EXISTS notes (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL, content TEXT NOT NULL, important INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, user_id BIGINT)""",
"""CREATE TABLE IF NOT EXISTS goals (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, target_date TEXT NOT NULL, progress INTEGER DEFAULT 0, status TEXT DEFAULT 'Active', user_id BIGINT)""",
"""CREATE TABLE IF NOT EXISTS reminders (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, reminder_date TEXT NOT NULL, reminder_time TEXT NOT NULL, status TEXT DEFAULT 'Pending', user_id BIGINT)""",
"""CREATE TABLE IF NOT EXISTS study_sessions (id BIGSERIAL PRIMARY KEY, subject TEXT NOT NULL, duration INTEGER NOT NULL, session_date TEXT NOT NULL, user_id BIGINT)""",
"""CREATE TABLE IF NOT EXISTS timetable (id BIGSERIAL PRIMARY KEY, entry_type TEXT NOT NULL, day TEXT NOT NULL, title TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, location TEXT DEFAULT '', teacher TEXT DEFAULT '', notes TEXT DEFAULT '', user_id BIGINT)""",
]

def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python migrate_sqlite_to_neon.py /path/to/database.db")
    src_path = Path(sys.argv[1]).expanduser().resolve()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not src_path.is_file(): sys.exit(f"SQLite file not found: {src_path}")
    if not url: sys.exit("DATABASE_URL is not set. Set it to your Neon connection string first.")
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    names = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, cols in TABLES.items():
        if table not in names: sys.exit(f"Source database is missing table: {table}")
        have = {r[1] for r in src.execute(f'PRAGMA table_info("{table}")')}
        missing = set(cols) - have
        if missing: sys.exit(f"Table {table} is missing columns: {', '.join(sorted(missing))}")
    counts = {t: src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in TABLES}
    print("Records found in SQLite:")
    for t, n in counts.items(): print(f"  {t}: {n}")
    if not counts["users"]: sys.exit("No user accounts found; migration stopped.")

    with psycopg.connect(url, row_factory=dict_row) as dst:
        with dst.cursor() as cur:
            for statement in SCHEMA: cur.execute(statement)
            for table in TABLES:
                cur.execute(f'SELECT COUNT(*) AS n FROM "{table}"')
                if cur.fetchone()["n"]:
                    sys.exit(f"Neon table {table} already has data. Nothing was imported; use an empty Neon database.")
        with dst.transaction():
            with dst.cursor() as cur:
                for table, cols in TABLES.items():
                    quoted = ", ".join(f'"{c}"' for c in cols)
                    marks = ", ".join(["%s"] * len(cols))
                    rows = src.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
                    if rows:
                        cur.executemany(f'INSERT INTO "{table}" ({quoted}) VALUES ({marks})',
                                        [tuple(row[c] for c in cols) for row in rows])
                for table in TABLES:
                    cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), GREATEST(COALESCE((SELECT MAX(id) FROM \"" + table + "\"), 1), 1), EXISTS (SELECT 1 FROM \"" + table + "\"))", (table,))
    src.close()
    print("Migration completed. Your SQLite source file was not modified.")
    print("Do not deploy the SQLite-based app.py as a PostgreSQL app; it must be converted separately first.")

if __name__ == "__main__": main()
