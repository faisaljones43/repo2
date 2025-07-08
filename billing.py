# billing.py
from datetime import date, timedelta
import database

def check_for_penalty(user_id: int, period_start: date, period_end: date) -> bool:
    """
    Checks if a user has skipped 4 consecutive days in a given period.
    A skip of 4 consecutive days means a gap of 5 days or more between check-ins.
    (e.g., Check-in on Mon, next is Sun. Skipped Tue, Wed, Thu, Fri. 4 days.)
    """
    conn = database.get_db_connection()
    # Fetch check-in dates for the user within the period
    check_in_rows = conn.execute(
        "SELECT DISTINCT date(check_in_timestamp) as check_in_date FROM check_ins WHERE user_id = ? AND date(check_in_timestamp) BETWEEN ? AND ?",
        (user_id, period_start.isoformat(), period_end.isoformat())
    ).fetchall()
    conn.close()

    if not check_in_rows:
        # If no check-ins at all, the gap is the whole month, which is > 4 days.
        return True

    # Convert rows to a sorted list of date objects
    check_in_dates = sorted([date.fromisoformat(row['check_in_date']) for row in check_in_rows])

    # Add period start and end to the list to check for gaps at the beginning and end
    all_dates = [period_start] + check_in_dates + [period_end]

    # Check the gap between each consecutive pair of dates
    for i in range(len(all_dates) - 1):
        gap = (all_dates[i+1] - all_dates[i]).days
        
        # A gap of 5 days means 4 full days were missed.
        # e.g., date1=1st, date2=6th. Gap = 5. Missed 2nd, 3rd, 4th, 5th.
        if gap >= 5:
            return True # Penalty triggered

    return False # No penalty-triggering gap found


def generate_monthly_invoices():
    """
    Main function to run the billing cycle. It iterates through all active users,
    calculates their bill for the previous month, and creates an invoice.
    """
    today = date.today()
    # For simplicity, let's assume we're billing for the previous calendar month.
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    billing_period_start = first_day_of_previous_month
    billing_period_end = last_day_of_previous_month
    
    users = database.get_all_users()
    invoices_created = []

    for user in users:
        if user['membership_status'] != 'active':
            continue

        base_fee = user['base_monthly_fee']
        penalty_amount = 0.0
        
        # Check if the user joined before the end of the billing period
        join_date = date.fromisoformat(user['join_date'])
        if join_date > billing_period_end:
            continue # Skip users who haven't been a member for the full period
        
        # Adjust the start of the check period if the user joined mid-month
        period_to_check_start = max(join_date, billing_period_start)

        has_penalty = check_for_penalty(user['id'], period_to_check_start, billing_period_end)

        if has_penalty:
            penalty_amount = base_fee * 0.20 # 20% penalty

        total_amount = base_fee + penalty_amount

        database.create_invoice(
            user_id=user['id'],
            period_start=billing_period_start,
            period_end=billing_period_end,
            base=base_fee,
            penalty=penalty_amount,
            total=total_amount
        )
        invoices_created.append({
            "name": user['name'],
            "base": base_fee,
            "penalty": penalty_amount,
            "total": total_amount
        })
    
    return invoices_created