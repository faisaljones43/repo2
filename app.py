# app.py
import streamlit as st
import pandas as pd
from datetime import datetime

import database
import billing

# --- APP SETUP ---
st.set_page_config(page_title="GymPro Billing", layout="wide")
st.title("🏋️ GymPro Automated Billing System")

# Initialize the database and create tables if they don't exist
database.setup_database()

# --- SIDEBAR FOR NAVIGATION AND ACTIONS ---
st.sidebar.header("Admin & User Actions")
app_mode = st.sidebar.selectbox("Choose a view", ["User Dashboard", "Admin Panel"])

# --- DATA SEEDING (for demonstration) ---
def seed_data():
    """Add some sample data if the DB is empty."""
    users = database.get_all_users()
    if not users:
        st.sidebar.warning("No users found. Seeding database with sample data.")
        database.add_user("Jim Halpert", "jim.h@dundermifflin.com", 50.00)
        database.add_user("Pam Beesly", "pam.b@dundermifflin.com", 50.00)
        database.add_user("Dwight Schrute", "dwight.s@dundermifflin.com", 60.00)
        st.sidebar.success("Sample users added!")
        st.rerun()

seed_data()

# --- USER DASHBOARD VIEW ---
if app_mode == "User Dashboard":
    st.header("👤 User Dashboard")
    
    users = database.get_all_users()
    user_list = {user['name']: user['id'] for user in users}
    selected_user_name = st.selectbox("Select a Gym Member", options=user_list.keys())
    
    if selected_user_name:
        user_id = user_list[selected_user_name]
        user_info = [u for u in users if u['id'] == user_id][0]

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"Welcome, {user_info['name']}!")
            st.write(f"**Email:** {user_info['email']}")
            st.write(f"**Member Since:** {user_info['join_date']}")
            st.write(f"**Base Monthly Fee:** ${user_info['base_monthly_fee']:.2f}")

            # Simulate scanning a card to check in
            if st.button("✔️ Scan to Check-In", key=f"checkin_{user_id}"):
                database.log_check_in(user_id)
                st.success(f"Checked in {user_info['name']} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                st.rerun()

        with col2:
            st.subheader("Check-in History")
            check_ins = database.get_user_check_ins(user_id)
            if check_ins:
                check_in_df = pd.DataFrame(check_ins, columns=["Check-in Time"])
                st.dataframe(check_in_df, use_container_width=True)
            else:
                st.info("No check-ins recorded yet.")

        st.markdown("---")
        st.subheader("Billing History")
        invoices = database.get_user_invoices(user_id)
        if invoices:
            invoice_df = pd.DataFrame(invoices).drop(columns=['id', 'user_id'])
            # Formatting for better display
            invoice_df['base_amount'] = invoice_df['base_amount'].apply(lambda x: f"${x:.2f}")
            invoice_df['penalty_amount'] = invoice_df['penalty_amount'].apply(lambda x: f"${x:.2f}")
            invoice_df['total_amount'] = invoice_df['total_amount'].apply(lambda x: f"${x:.2f}")
            st.dataframe(invoice_df, use_container_width=True)
        else:
            st.info("No invoices generated yet.")

# --- ADMIN PANEL VIEW ---
elif app_mode == "Admin Panel":
    st.header("⚙️ Admin Panel")

    # Section to add a new user
    with st.expander("➕ Add a New Gym Member"):
        with st.form("new_user_form", clear_on_submit=True):
            name = st.text_input("Full Name")
            email = st.text_input("Email Address")
            base_fee = st.number_input("Base Monthly Fee ($)", min_value=0.0, step=1.00, format="%.2f")
            submitted = st.form_submit_button("Add Member")
            if submitted:
                if name and email and base_fee > 0:
                    database.add_user(name, email, base_fee)
                    st.success(f"Successfully added {name}!")
                else:
                    st.error("Please fill out all fields.")

    # Section to run the billing cycle
    st.subheader("💰 Monthly Billing Cycle")
    st.info("This process will generate invoices for the *previous* calendar month for all active members.")
    if st.button("Run Monthly Billing Process"):
        with st.spinner("Generating invoices... This may take a moment."):
            invoices_created = billing.generate_monthly_invoices()
        st.success("Billing cycle completed!")
        if invoices_created:
            st.write("Summary of Invoices Created:")
            summary_df = pd.DataFrame(invoices_created)
            st.dataframe(summary_df)
        else:
            st.warning("No new invoices were created. This could be because users are new or billing has already run.")