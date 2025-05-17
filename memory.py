import os, sqlite3, json

DB = os.getenv("USER_DB_PATH", "user_prefs.db")
_conn = sqlite3.connect(DB, check_same_thread=False)
_conn.execute("""
  CREATE TABLE IF NOT EXISTS preferences (
    user_id    TEXT PRIMARY KEY,
    prefs      TEXT  
)
""")
_conn.commit()

def save_prefs(user_id: str, prefs: dict):
    _conn.execute(
        "REPLACE INTO preferences (user_id, prefs) VALUES (?,?)",
        (user_id, json.dumps(prefs))
    )
    _conn.commit()

def recall_prefs(user_id: str) -> dict | None:
    cur = _conn.execute(
        "SELECT prefs FROM preferences WHERE user_id=?", (user_id,)
    )
    row = cur.fetchone()
    return json.loads(row[0]) if row else None
