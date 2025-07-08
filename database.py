# database.py
import sqlite3
from datetime import date

DB_NAME = "gym_database.db"

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Creates the necessary tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            join_date TEXT NOT NULL,
            base_monthly_fee REAL NOT NULL,
            membership_status TEXT NOT NULL DEFAULT 'active'
        )
    ''')

    # Check-ins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS check_ins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            check_in_timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Invoices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            billing_period_start TEXT NOT NULL,
            billing_period_end TEXT NOT NULL,
            base_amount REAL NOT NULL,
            penalty_amount REAL NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            issue_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database setup complete.")

def add_user(name, email, base_fee):
    """Adds a new user to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, join_date, base_monthly_fee) VALUES (?, ?, ?, ?)",
        (name, email, date.today().isoformat(), base_fee)
    )
    conn.commit()
    conn.close()

def log_check_in(user_id):
    """Logs a check-in for a given user."""
    from datetime import datetime
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO check_ins (user_id, check_in_timestamp) VALUES (?, ?)",
        (user_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_all_users():
    """Retrieves all users from the database."""
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return users

def get_user_check_ins(user_id):
    """Retrieves all check-ins for a specific user."""
    conn = get_db_connection()
    check_ins = conn.execute(
        "SELECT check_in_timestamp FROM check_ins WHERE user_id = ? ORDER BY check_in_timestamp DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return check_ins

def get_user_invoices(user_id):
    """Retrieves all invoices for a specific user."""
    conn = get_db_connection()
    invoices = conn.execute(
        "SELECT * FROM invoices WHERE user_id = ? ORDER BY issue_date DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return invoices

def create_invoice(user_id, period_start, period_end, base, penalty, total):
    """Creates a new invoice record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO invoices (user_id, billing_period_start, billing_period_end, base_amount, penalty_amount, total_amount, issue_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, period_start.isoformat(), period_end.isoformat(), base, penalty, total, date.today().isoformat())
    )
    conn.commit()
    conn.close()