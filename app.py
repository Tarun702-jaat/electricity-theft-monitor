import pandas as pd
import hashlib
import hmac
import os
import re
import secrets
import smtplib
from email.message import EmailMessage
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from datetime import date
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import engine as E

st.set_page_config(page_title="POWERGUARD GLOBAL", page_icon="⚡", layout="wide")

BLUE = "#2563eb"
ORANGE = "#f59e0b"
RED = "#dc2626"
GREEN = "#16a34a"
GREY = "#94a3b8"
NAVY = "#0b132b"
SLATE = "#1f2937"
SEV_COLOR = {"High": RED, "Medium": ORANGE, "Low": "#eab308", "Normal": GREEN}

# Built-in English/Hindi interface language support.
UI_TEXT = {
    "English": {},
    "हिन्दी": {
        "Overview": "मुख्य जानकारी", "UHBVN Consumer Help": "UHBVN उपभोक्ता सहायता",
        "My Consumer Dashboard": "मेरा उपभोक्ता डैशबोर्ड", "India Monitoring": "भारत निगरानी",
        "Theft Detection": "बिजली चोरी पहचान", "Data Centre": "डेटा केंद्र",
        "News Intelligence": "समाचार और जानकारी", "Reports": "रिपोर्ट",
        "Navigation": "नेविगेशन", "Energy Intelligence Platform": "ऊर्जा जानकारी प्लेटफ़ॉर्म",
        "Data note: demo and public reference values are shown unless live utility integration is connected.": "डेटा सूचना: लाइव बिजली विभाग कनेक्शन उपलब्ध न होने पर डेमो और सार्वजनिक संदर्भ डेटा दिखाया जाता है।",
        "My electricity connection": "मेरा बिजली कनेक्शन", "Add a bill to your records": "अपने रिकॉर्ड में बिल जोड़ें",
        "My electricity history": "मेरे बिजली बिल का इतिहास", "Bill affordability and usage insights": "बिल और बिजली उपयोग का विश्लेषण",
        "Your next-bill planning estimate": "अगले बिल का अनुमान", "Electricity-saving suggestions": "बिजली बचाने के सुझाव",
        "How to understand your electricity bill": "अपना बिजली बिल कैसे समझें", "Check your meter units": "मीटर की यूनिट जाँचें",
        "Trust Reading: what consumers should know": "ट्रस्ट रीडिंग: उपभोक्ताओं के लिए जानकारी",
        "Common problems and what to do": "आम समस्याएँ और क्या करें",
        "How to pay / fill in the online bill-payment form": "ऑनलाइन बिजली बिल का भुगतान कैसे करें",
        "Prepare a complaint": "शिकायत तैयार करें", "UHBVN consumer contact": "UHBVN उपभोक्ता संपर्क",
        "Consumer rights and escalation": "उपभोक्ता अधिकार और शिकायत आगे बढ़ाना",
        "Tariff and public information": "बिजली दरें और सार्वजनिक जानकारी",
        "Sign in": "लॉग इन करें", "Create account": "खाता बनाएँ", "Email address": "ईमेल पता",
        "Create my account": "मेरा खाता बनाएँ", "Sign out": "लॉग आउट",
        "Save connection details": "कनेक्शन की जानकारी सेव करें",
        "Save bill to my dashboard": "बिल मेरे डैशबोर्ड में सेव करें",
        "Download my bill history (CSV)": "मेरे बिल का इतिहास डाउनलोड करें (CSV)",
        "Language / भाषा": "भाषा / Language",
    },
}
def _t(label):
    return UI_TEXT.get(st.session_state.get("app_language", "English"), {}).get(label, label)


st.markdown(
    """
    <style>
        :root {
            --bg: #07111d;
            --panel: #111827;
            --panel-soft: #0f172a;
            --line: rgba(148,163,184,.18);
            --text: #e5eefb;
            --muted: #9db0cc;
            --blue: #3b82f6;
            --green: #22c55e;
            --orange: #f59e0b;
            --red: #ef4444;
        }
        html, body, [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #07111d 0%, #0c1728 100%);
            color: var(--text);
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        .card {
            background: rgba(15,23,42,0.95);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 25px rgba(15,23,42,0.18);
        }
        div[data-testid="stMetric"] {
            background: rgba(15,23,42,0.9);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 12px 14px;
        }
        .alert-card {
            border-left: 5px solid;
            padding: 12px 14px;
            margin: 8px 0;
            border-radius: 10px;
            background: rgba(15,23,42,0.75);
            border-top: 1px solid rgba(148,163,184,.12);
            border-right: 1px solid rgba(148,163,184,.12);
            border-bottom: 1px solid rgba(148,163,184,.12);
        }
        .alert-card small { opacity: .8; }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 999px;
            background: rgba(59,130,246,0.12);
            color: #cfe2ff;
            border: 1px solid rgba(59,130,246,0.2);
            font-size: 11px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .small-muted { color: var(--muted); }
    </style>
    """,
    unsafe_allow_html=True,
)



# Personal consumer portal storage. Set POWERGUARD_DATA_DIR to a persistent,
# access-controlled directory in production; Streamlit Cloud local disk is ephemeral.
def _consumer_db_path():
    configured_dir = os.environ.get("POWERGUARD_DATA_DIR")
    base = Path(configured_dir).expanduser() if configured_dir else Path(__file__).with_name("powerguard_data")
    base.mkdir(parents=True, exist_ok=True)
    return base / "consumer_portal.sqlite3"


@contextmanager
def _consumer_db():
    conn = sqlite3.connect(_consumer_db_path(), timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_consumer_db():
    with _consumer_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consumer_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consumer_profiles (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL DEFAULT '',
                utility TEXT NOT NULL DEFAULT 'UHBVN',
                category TEXT NOT NULL DEFAULT 'Domestic',
                connection_label TEXT NOT NULL DEFAULT '',
                sanctioned_load TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES consumer_users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consumer_bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bill_month TEXT NOT NULL,
                units_kwh REAL NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                file_name TEXT NOT NULL DEFAULT '',
                file_bytes BLOB,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES consumer_users(id) ON DELETE CASCADE
            )
        """)
        # Safe schema upgrades for existing prototype databases.
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(consumer_users)").fetchall()}
        if "email_verified" not in user_columns:
            conn.execute("ALTER TABLE consumer_users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        bill_columns = {row["name"] for row in conn.execute("PRAGMA table_info(consumer_bills)").fetchall()}
        if "payment_status" not in bill_columns:
            conn.execute("ALTER TABLE consumer_bills ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'Unmarked'")
        if "payment_date" not in bill_columns:
            conn.execute("ALTER TABLE consumer_bills ADD COLUMN payment_date TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_consumer_bills_user ON consumer_bills(user_id, bill_month)")


def _password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)


def _create_consumer_account(email, password):
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        return False, "Enter a valid email address."
    if len(password) < 10:
        return False, "Use a password with at least 10 characters."
    salt = secrets.token_bytes(16)
    digest = _password_digest(password, salt)
    try:
        with _consumer_db() as conn:
            cur = conn.execute(
                "INSERT INTO consumer_users(email, salt, password_hash) VALUES (?, ?, ?)",
                (normalized, salt, digest),
            )
            user_id = cur.lastrowid
            conn.execute("INSERT INTO consumer_profiles(user_id) VALUES (?)", (user_id,))
        return True, (user_id, normalized)
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists. Please sign in."


def _authenticate_consumer(email, password):
    with _consumer_db() as conn:
        row = conn.execute(
            "SELECT id, email, salt, password_hash FROM consumer_users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if row is None:
        return None
    candidate = _password_digest(password, row["salt"])
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None
    return (row["id"], row["email"])


def _mail_setting(name, default=""):
    value = os.environ.get(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _send_consumer_email_otp(email, code):
    """Send an email ownership code. Configure SMTP_* secrets in Streamlit."""
    host = _mail_setting("SMTP_HOST")
    port = int(_mail_setting("SMTP_PORT", "587"))
    username = _mail_setting("SMTP_USERNAME")
    password = _mail_setting("SMTP_PASSWORD")
    sender = _mail_setting("SMTP_FROM", username)
    if not all([host, username, password, sender]):
        return False, "Email verification is not configured yet. The site owner must add SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM in Streamlit Secrets."
    message = EmailMessage()
    message["Subject"] = "Your POWERGUARD verification code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your POWERGUARD email verification code is {code}. "
        "It expires in 5 minutes. Do not share this code with anyone. "
        "This verifies your email address only; it does not verify a UHBVN electricity connection."
    )
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)
        return True, "Verification code sent to your email."
    except Exception:
        return False, "Could not send the email. Check the SMTP settings in Streamlit Secrets."


def _email_is_verified(user_id):
    with _consumer_db() as conn:
        row = conn.execute(
            "SELECT email_verified FROM consumer_users WHERE id = ?", (user_id,)
        ).fetchone()
    return bool(row and row["email_verified"])


def _render_email_verification(user_id, email):
    st.subheader("Verify your email address")
    st.info("A one-time code will be sent to your email. This confirms email access only, not UHBVN account ownership.")
    if st.button("Send email verification code", key="send_consumer_email_otp"):
        now = time.time()
        last_sent = float(st.session_state.get("consumer_email_otp_sent_at", 0))
        if now - last_sent < 60:
            st.warning("Please wait 60 seconds before requesting another code.")
        else:
            code = f"{secrets.randbelow(1000000):06d}"
            ok, message = _send_consumer_email_otp(email, code)
            if ok:
                st.session_state.consumer_email_otp_hash = hashlib.sha256((email + ":" + code).encode()).hexdigest()
                st.session_state.consumer_email_otp_expiry = now + 300
                st.session_state.consumer_email_otp_attempts = 0
                st.session_state.consumer_email_otp_sent_at = now
                st.success(message)
            else:
                st.error(message)
    if st.session_state.get("consumer_email_otp_hash"):
        with st.form("consumer_email_verify_form"):
            entered = st.text_input("Enter the 6-digit code sent to your email", max_chars=6)
            submitted = st.form_submit_button("Verify email", use_container_width=True)
        if submitted:
            attempts = int(st.session_state.get("consumer_email_otp_attempts", 0))
            expected = st.session_state.consumer_email_otp_hash
            candidate = hashlib.sha256((email + ":" + entered.strip()).encode()).hexdigest()
            if time.time() > float(st.session_state.get("consumer_email_otp_expiry", 0)):
                st.session_state.pop("consumer_email_otp_hash", None)
                st.error("Code expired. Request a new code.")
            elif attempts >= 5:
                st.session_state.pop("consumer_email_otp_hash", None)
                st.error("Too many attempts. Request a new code later.")
            elif re.fullmatch(r"\d{6}", entered.strip()) and hmac.compare_digest(candidate, expected):
                with _consumer_db() as conn:
                    conn.execute("UPDATE consumer_users SET email_verified = 1 WHERE id = ?", (user_id,))
                st.session_state.pop("consumer_email_otp_hash", None)
                st.success("Email verified successfully.")
                st.rerun()
            else:
                st.session_state.consumer_email_otp_attempts = attempts + 1
                st.error("Incorrect code.")
    st.caption("If this account is for a UHBVN connection, complete consumer KYC separately on the official UHBVN portal.")


def _render_consumer_portal():
    _init_consumer_db()
    st.title(_t("My Consumer Dashboard"))
    st.caption("A private, account-based space for the electricity information you choose to save.")
    st.warning(
        "Prototype storage notice: this version stores records in a local SQLite database on the app server. "
        "Streamlit Cloud may reset local files, so do not upload real bills or sensitive personal information "
        "until a persistent production database and deployment security review are configured."
    )

    if "consumer_user_id" not in st.session_state:
        st.session_state.consumer_user_id = None
        st.session_state.consumer_email = None

    if st.session_state.consumer_user_id is None:
        login_tab, register_tab = st.tabs(["Sign in", "Create account"])
        with login_tab:
            with st.form("consumer_login_form"):
                login_email = st.text_input("Email address", key="consumer_login_email")
                login_password = st.text_input("Password", type="password", key="consumer_login_password")
                login_submit = st.form_submit_button("Sign in", use_container_width=True)
            if login_submit:
                account = _authenticate_consumer(login_email, login_password)
                if account:
                    st.session_state.consumer_user_id, st.session_state.consumer_email = account
                    st.rerun()
                else:
                    st.error("Email or password is incorrect.")
        with register_tab:
            with st.form("consumer_register_form"):
                new_email = st.text_input("Email address", key="consumer_register_email")
                new_password = st.text_input("Create password (10+ characters)", type="password")
                confirm_password = st.text_input("Confirm password", type="password")
                register_submit = st.form_submit_button("Create my account", use_container_width=True)
            if register_submit:
                if new_password != confirm_password:
                    st.error("The passwords do not match.")
                else:
                    ok, result = _create_consumer_account(new_email, new_password)
                    if ok:
                        st.session_state.consumer_user_id, st.session_state.consumer_email = result
                        st.success("Account created.")
                        st.rerun()
                    else:
                        st.error(result)
        st.info("Each signed-in account can access only records linked to its own account in this app.")
        st.caption("Email verification is required after sign-in. The site owner must configure SMTP settings in Streamlit Secrets. Do not reuse a password from another service.")
        return

    user_id = int(st.session_state.consumer_user_id)
    if not _email_is_verified(user_id):
        _render_email_verification(user_id, st.session_state.consumer_email)
        if st.button("Sign out", key="unverified_consumer_sign_out"):
            st.session_state.consumer_user_id = None
            st.session_state.consumer_email = None
            st.rerun()
        st.stop()

    st.write(f"Signed in as **{st.session_state.consumer_email}**")
    if st.button("Sign out", key="consumer_sign_out"):
        st.session_state.consumer_user_id = None
        st.session_state.consumer_email = None
        st.rerun()

    with _consumer_db() as conn:
        profile = conn.execute(
            "SELECT * FROM consumer_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    profile = dict(profile) if profile else {}

    # Demo-only verification workflow. No SMS is sent and no UHBVN records are queried.
    st.subheader("Consumer connection check")
    st.warning(
        "Demo verification only: this test does not contact UHBVN, send an SMS, or confirm that "
        "the consumer number belongs to you. Do not enter a full account number or phone number."
    )
    with st.expander("Try the consumer verification demo", expanded=not st.session_state.get("consumer_demo_check_passed", False)):
        st.markdown("Enter only the last four digits of your consumer number and registered mobile number.")
        with st.form("consumer_demo_start_form"):
            account_last4 = st.text_input("Last 4 digits of consumer number", max_chars=4)
            mobile_last4 = st.text_input("Last 4 digits of registered mobile", max_chars=4)
            start_demo = st.form_submit_button("Start demo verification")
        if start_demo:
            if not (re.fullmatch(r"\d{4}", account_last4.strip()) and re.fullmatch(r"\d{4}", mobile_last4.strip())):
                st.error("Enter exactly four digits in both fields.")
            else:
                st.session_state.consumer_demo_account_last4 = account_last4.strip()
                st.session_state.consumer_demo_mobile_last4 = mobile_last4.strip()
                st.session_state.consumer_demo_otp = f"{secrets.randbelow(1000000):06d}"
                st.session_state.consumer_demo_otp_expiry = time.time() + 180
                st.session_state.consumer_demo_attempts = 0
                st.session_state.consumer_demo_check_passed = False
                st.info("A demo code has been generated below. It is displayed here because this prototype cannot send SMS.")
        if st.session_state.get("consumer_demo_otp"):
            if time.time() > st.session_state.get("consumer_demo_otp_expiry", 0):
                st.error("Demo code expired. Start the demo again.")
                st.session_state.pop("consumer_demo_otp", None)
            elif not st.session_state.get("consumer_demo_check_passed", False):
                st.code(st.session_state.consumer_demo_otp, language=None)
                with st.form("consumer_demo_otp_form"):
                    entered_demo_otp = st.text_input("Enter the 6-digit demo code", max_chars=6)
                    verify_demo = st.form_submit_button("Verify demo code")
                if verify_demo:
                    attempts = int(st.session_state.get("consumer_demo_attempts", 0))
                    if attempts >= 5:
                        st.error("Maximum attempts reached. Start the demo again.")
                        st.session_state.pop("consumer_demo_otp", None)
                    elif hmac.compare_digest(entered_demo_otp.strip(), st.session_state.consumer_demo_otp):
                        st.session_state.consumer_demo_check_passed = True
                        st.session_state.pop("consumer_demo_otp", None)
                        st.success("Demo contact-check completed for this session. This is not official UHBVN verification.")
                    else:
                        st.session_state.consumer_demo_attempts = attempts + 1
                        st.error("Incorrect demo code. Please try again.")
        if st.session_state.get("consumer_demo_check_passed", False):
            st.success(
                "Demo status: contact-check workflow completed. "
                f"Consumer reference ending {st.session_state.get('consumer_demo_account_last4', '----')}."
            )
        st.markdown("[Complete actual consumer KYC on the official UHBVN portal](https://epayment.uhbvn.org.in/updateKYC.aspx)")
        st.caption("For real verification, UHBVN must confirm the account and registered mobile through its authorised service. This demo status is temporary and is not stored as an official verified identity.")

    st.subheader("1. My electricity connection")
    with st.form("consumer_profile_form"):
        p1, p2 = st.columns(2)
        with p1:
            full_name = st.text_input("Name / profile label", value=profile.get("full_name", ""))
            utility = st.selectbox(
                "Electricity provider",
                ["UHBVN", "DHBVN", "Other"],
                index=["UHBVN", "DHBVN", "Other"].index(profile.get("utility", "UHBVN"))
                if profile.get("utility", "UHBVN") in ["UHBVN", "DHBVN", "Other"] else 0,
            )
            category = st.selectbox(
                "Connection category",
                ["Domestic", "Non-domestic", "LT Industrial", "Agriculture", "Other"],
                index=["Domestic", "Non-domestic", "LT Industrial", "Agriculture", "Other"].index(profile.get("category", "Domestic"))
                if profile.get("category", "Domestic") in ["Domestic", "Non-domestic", "LT Industrial", "Agriculture", "Other"] else 0,
            )
        with p2:
            connection_label = st.text_input(
                "Connection nickname / last 4 digits only",
                value=profile.get("connection_label", ""),
                help="Do not enter your full account number, Aadhaar, phone number, OTP or password.",
            )
            sanctioned_load = st.text_input("Sanctioned load (optional)", value=profile.get("sanctioned_load", ""))
        save_profile = st.form_submit_button("Save connection details")
    if save_profile:
        with _consumer_db() as conn:
            conn.execute("""
                INSERT INTO consumer_profiles(user_id, full_name, utility, category, connection_label, sanctioned_load, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name=excluded.full_name, utility=excluded.utility,
                    category=excluded.category, connection_label=excluded.connection_label,
                    sanctioned_load=excluded.sanctioned_load, updated_at=CURRENT_TIMESTAMP
            """, (user_id, full_name.strip()[:100], utility, category, connection_label.strip()[:40], sanctioned_load.strip()[:40]))
        st.success("Your connection profile has been saved.")

    st.divider()
    st.subheader("2. Add a bill to your records")
    st.caption("Enter the figures printed on your bill. You may attach a PDF or image for your own reference; this prototype does not automatically read/OCR the document.")
    with st.form("consumer_bill_form"):
        bill_month = st.date_input("Bill date / month", value=date.today())
        b1, b2, b3 = st.columns(3)
        with b1:
            units = st.number_input("Units consumed (kWh)", min_value=0.0, value=0.0, step=1.0)
        with b2:
            amount = st.number_input("Bill amount (₹)", min_value=0.0, value=0.0, step=100.0)
        with b3:
            due_date = st.date_input("Payment due date", value=date.today(), key="consumer_bill_due")
        notes = st.text_area("Notes (optional)", max_chars=500, placeholder="Example: monthly bill, estimated reading, payment note…")
        payment_status = st.selectbox("Payment status", ["Unmarked", "Paid", "Unpaid", "Disputed"])
        payment_date = st.date_input("Payment date (if paid)", value=date.today(), key="consumer_payment_date")
        bill_file = st.file_uploader("Attach bill copy (optional, PDF/JPG/PNG, max 5 MB)", type=["pdf", "jpg", "jpeg", "png"], key="consumer_bill_upload")
        save_bill = st.form_submit_button("Save bill to my dashboard")
    if save_bill:
        if bill_file is not None and bill_file.size > 5 * 1024 * 1024:
            st.error("The attachment exceeds the 5 MB limit.")
        else:
            payload = bill_file.getvalue() if bill_file is not None else None
            filename = bill_file.name[:180] if bill_file is not None else ""
            with _consumer_db() as conn:
                conn.execute("""
                    INSERT INTO consumer_bills(user_id, bill_month, units_kwh, amount, due_date, notes, file_name, file_bytes, payment_status, payment_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, bill_month.isoformat(), float(units), float(amount),
                    due_date.isoformat(), notes.strip(), filename, payload,
                    payment_status, payment_date.isoformat() if payment_status == "Paid" else "",
                ))
            st.success("Bill record saved to your account.")

    st.divider()
    st.subheader("3. My electricity history")
    with _consumer_db() as conn:
        bill_rows = conn.execute("""
            SELECT id, bill_month, units_kwh, amount, due_date, notes, file_name, payment_status, payment_date
            FROM consumer_bills WHERE user_id = ? ORDER BY bill_month DESC, id DESC
        """, (user_id,)).fetchall()
    if not bill_rows:
        st.info("You have not saved any bill records yet. Add your first bill above.")
        return

    bills_df = pd.DataFrame([dict(row) for row in bill_rows])
    total_units = float(bills_df["units_kwh"].sum())
    total_amount = float(bills_df["amount"].sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Saved bills", len(bills_df))
    m2.metric("Total recorded units", f"{total_units:,.1f} kWh")
    m3.metric("Total recorded bill amount", f"₹{total_amount:,.2f}")
    unpaid = bills_df[bills_df["payment_status"].isin(["Unpaid", "Unmarked"])]
    m4.metric("Unpaid / unmarked bills", len(unpaid))
    if not unpaid.empty:
        st.warning(f"You have {len(unpaid)} bill record(s) marked unpaid or unmarked. Verify the current balance on the official UHBVN portal before paying.")
    paid_total = float(bills_df.loc[bills_df["payment_status"] == "Paid", "amount"].sum())
    avg_units = float(bills_df["units_kwh"].mean()) if len(bills_df) else 0.0
    avg_amount = float(bills_df["amount"].mean()) if len(bills_df) else 0.0
    k1, k2, k3 = st.columns(3)
    k1.metric("Recorded paid amount", f"₹{paid_total:,.2f}")
    k2.metric("Average units per bill", f"{avg_units:,.1f} kWh")
    k3.metric("Average bill amount", f"₹{avg_amount:,.2f}")
    chart_df = bills_df.copy()
    chart_df["bill_month"] = pd.to_datetime(chart_df["bill_month"], errors="coerce")
    chart_df = chart_df.dropna(subset=["bill_month"]).sort_values("bill_month")
    if not chart_df.empty:
        st.plotly_chart(
            px.line(chart_df, x="bill_month", y="units_kwh", markers=True, title="My monthly electricity consumption (kWh)"),
            use_container_width=True,
        )
        st.plotly_chart(
            px.bar(chart_df, x="bill_month", y="amount", title="My saved bill amounts (₹)"),
            use_container_width=True,
        )
    st.dataframe(
        bills_df[["bill_month", "units_kwh", "amount", "due_date", "payment_status", "payment_date", "notes", "file_name"]],
        hide_index=True, use_container_width=True,
    )
    st.download_button(
        "Download my bill history (CSV)",
        bills_df.drop(columns=["id"], errors="ignore").to_csv(index=False).encode("utf-8"),
        "my_electricity_bill_history.csv",
        "text/csv",
        use_container_width=True,
    )
    st.subheader(_t("Bill affordability and usage insights"))
    if avg_units > 0:
        st.write(f"Your recorded average usage is **{avg_units:,.1f} kWh per bill**. Your recorded average bill is **₹{avg_amount:,.2f}**.")
        if len(bills_df) >= 2:
            latest = bills_df.iloc[0]
            previous = bills_df.iloc[1]
            change = float(latest["units_kwh"]) - float(previous["units_kwh"])
            if change > 0:
                st.info(f"Your latest saved bill has {change:,.1f} more units than the previous saved bill.")
            elif change < 0:
                st.success(f"Your latest saved bill has {abs(change):,.1f} fewer units than the previous saved bill.")
            else:
                st.info("Your latest and previous saved bills show the same recorded usage.")
        st.caption("Insights are calculated only from bills you entered. They are not utility meter telemetry or a tariff-based forecast.")

    st.subheader(_t("Your next-bill planning estimate"))
    if len(bills_df) >= 2 and avg_units > 0:
        recent = bills_df.head(min(3, len(bills_df)))
        forecast_units = float(recent["units_kwh"].mean())
        recent_unit_costs = [
            float(row["amount"]) / float(row["units_kwh"])
            for _, row in recent.iterrows()
            if float(row["units_kwh"]) > 0
        ]
        indicative_rate = sum(recent_unit_costs) / len(recent_unit_costs) if recent_unit_costs else 0.0
        forecast_amount = forecast_units * indicative_rate
        f1, f2 = st.columns(2)
        f1.metric("Planning usage estimate", f"{forecast_units:,.1f} kWh")
        f2.metric("Indicative bill estimate", f"₹{forecast_amount:,.0f}" if indicative_rate else "Not available")
        st.caption("Simple estimate from your latest saved bills: recent average units × your historical average bill-per-unit. Actual bills can differ due to tariff slabs, fixed charges, taxes, adjustments, season, meter multiplier and billing days. This is not an official UHBVN forecast.")
    else:
        st.info("Save at least two monthly bills to unlock a basic next-bill planning estimate.")

    st.subheader("Personalised ways to reduce electricity use")
    if len(bills_df) >= 2:
        latest_units = float(bills_df.iloc[0]["units_kwh"])
        previous_units = float(bills_df.iloc[1]["units_kwh"])
        if previous_units > 0 and latest_units > previous_units * 1.10:
            st.warning("Your latest recorded usage is more than 10% above the previous bill. Check whether billing days, weather, guests or appliance use changed before assuming there is a fault.")
            st.write("- Compare the billing-period dates and meter readings first.\n- Check high-use appliances such as air conditioners, water heaters, pumps and room heaters.\n- Use AC at a moderate comfortable setting, clean filters as recommended and keep doors/windows closed while cooling.\n- Switch off lights and devices when not needed; avoid leaving chargers and electronics on unnecessarily.")
        elif latest_units < previous_units:
            st.success("Your latest saved bill shows lower usage than the previous one. Continue checking monthly readings and billing days.")
        else:
            st.info("Your recent recorded usage is broadly similar. Small changes in billing days or weather can affect comparisons.")
    else:
        st.write("- Prefer LED lights and switch off lights/fans in empty rooms.\n- Use efficient appliances and their energy-saving modes where suitable.\n- Set AC to a comfortable moderate temperature and clean filters regularly.\n- Run washing machines with suitable full loads and avoid unnecessary hot-water use.\n- Check pump, geyser and room-heater timers; avoid leaving them on longer than needed.")
    st.caption("Tips are general energy-efficiency guidance, not guaranteed savings. Never touch exposed wiring, open a meter or interfere with utility equipment.")

    attached = bills_df[bills_df["file_name"].astype(str).ne("")]
    if not attached.empty:
        st.subheader("My uploaded bill copies")
        selected_id = st.selectbox(
            "Choose an attachment",
            attached["id"].tolist(),
            format_func=lambda value: f"Bill #{value} — {attached.loc[attached['id'] == value, 'file_name'].iloc[0]}",
        )
        with _consumer_db() as conn:
            file_row = conn.execute(
                "SELECT file_name, file_bytes FROM consumer_bills WHERE id = ? AND user_id = ?",
                (int(selected_id), user_id),
            ).fetchone()
        if file_row and file_row["file_bytes"] is not None:
            suffix = Path(file_row["file_name"]).suffix.lower()
            mime = "application/pdf" if suffix == ".pdf" else "image/png" if suffix == ".png" else "image/jpeg"
            st.download_button(
                "Download my bill copy",
                data=file_row["file_bytes"],
                file_name=file_row["file_name"],
                mime=mime,
                use_container_width=True,
            )

    st.caption("Your dashboard displays only information entered or uploaded by you. It is not a live UHBVN/DHBVN account connection, official bill, payment service or theft determination.")

app_summary = E.get_global_overview()
india_summary = E.get_india_monitoring()
news_items = E.get_news_feed()

with st.sidebar:
    st.title("POWERGUARD GLOBAL")
    st.caption("Energy Intelligence Platform")
    st.selectbox(
        "Language / भाषा",
        ["English", "हिन्दी"],
        key="app_language",
        help="Choose English or Hindi for navigation and translated section headings.",
    )
    page = st.radio(
        _t("Navigation"),
        [
            "Overview",
            "UHBVN Consumer Help",
            "My Consumer Dashboard",
            "India Monitoring",
            "Theft Detection",
            "Data Centre",
            "News Intelligence",
            "Reports",
        ],
        format_func=_t,
    )
    st.divider()
    st.caption(_t("Data note: demo and public reference values are shown unless live utility integration is connected."))


# Keep the personal portal independent of the global demo/CSV data selector.
if page == "My Consumer Dashboard":
    _render_consumer_portal()
    st.stop()

# Shared utility / simulation input
with st.sidebar:
    st.subheader("Data Source")
    source = st.radio("Use", ["Simulated meter data", "Upload CSV", "Saved database"], label_visibility="collapsed")

    if source == "Simulated meter data":
        n_cons = st.slider("Consumers", 10, 100, 30, 5)
        n_days = st.slider("Days", 7, 60, 14)
        seed = st.number_input("Random seed", 0, 9999, 42)
        raw, truth = E.make_demo_data(n_cons, n_days, int(seed))
    elif source == "Upload CSV":
        st.caption("Columns: day, consumer_id, expected_kwh, meter_kwh (optional: category)")
        up = st.file_uploader("CSV file", type="csv")
        if up is None:
            st.info("Upload a CSV in the sidebar, or switch to Simulated meter data.")
            st.stop()
        raw, truth = pd.read_csv(up), None
    else:
        raw, truth = E.load_from_db(), None
        if raw is None:
            st.info("No saved data yet. Analyse some data first and press Save to database in the Reports page.")
            st.stop()

    st.subheader("Detection")
    threshold = st.slider("Deviation threshold (%)", 5, 60, 25)
    contamination = st.slider("ML sensitivity", 0.01, 0.15, 0.04, 0.01)
    tech_loss = st.slider("Technical loss (%)", 0.0, 20.0, 6.0, 0.5)
    tolerance = st.slider("Energy-balance tolerance (%)", 0.5, 10.0, 3.0, 0.5)
    override = st.number_input("Feeder supply override (kWh/day, 0 = use data)", 0.0, 1e7, 0.0, 100.0)

@st.cache_data(show_spinner="Analysing readings…")
def run(raw_df, threshold, contamination, tech_loss, tolerance, override):
    clean, errors, dropped = E.validate(raw_df)
    if errors:
        return None, None, errors, dropped
    a = E.analyse(clean, threshold, contamination)
    b = E.feeder_balance(a, tech_loss, tolerance, override or None)
    return a, b, [], dropped

analysed, balance, errors, dropped = run(raw, threshold, contamination, tech_loss, tolerance, override)
if errors:
    for e in errors:
        st.error(e)
    st.stop()
if dropped:
    st.warning(f"{dropped} invalid row(s) were excluded during validation.")

alerts = analysed[analysed["flagged"]].copy()
days = sorted(analysed["day"].unique())


def plot_style(fig, h=380):
    fig.update_layout(
        height=h,
        margin=dict(l=8, r=8, t=40, b=8),
        legend=dict(orientation="h", y=-0.2),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5eefb"),
    )
    return fig


if page == "Overview":
    st.title("POWERGUARD GLOBAL")
    st.caption("Smart Electricity Theft Detection & Energy Intelligence Platform")
    st.markdown('<div class="badge">Simulated / public reference data only</div>', unsafe_allow_html=True)

    st.subheader("Global overview")
    c = st.columns(5)
    c[0].metric("Total demand", f"{app_summary['consumption_total']:,.0f} GWh")
    c[1].metric("Distribution losses", f"{app_summary['loss_total']:,.0f} GWh")
    c[2].metric("Suspicious activity", f"{app_summary['suspicious_total']:,}")
    c[3].metric("Regional alerts", f"{app_summary['alert_total']:,}")
    c[4].metric("Coverage", app_summary["coverage"])

    st.subheader("Regional performance")
    reg_df = app_summary["regions"]
    fig = px.bar(
        reg_df,
        x="region",
        y="loss_pct",
        color="loss_pct",
        color_continuous_scale="RdYlGn_r",
        title="Regional loss exposure (%)",
    )
    st.plotly_chart(plot_style(fig, 400), use_container_width=True)

    left, right = st.columns(2)
    with left:
        geo = app_summary["countries"]
        fig = px.bar(
            geo,
            x="country",
            y="consumption_gwh",
            color="country",
            title="Electricity consumption by country",
        )
        st.plotly_chart(plot_style(fig, 400), use_container_width=True)
    with right:
        fig = px.pie(
            geo,
            names="country",
            values="loss_gwh",
            title="Loss contribution by country",
        )
        st.plotly_chart(plot_style(fig, 400), use_container_width=True)

    st.subheader("Live monitoring interface")
    st.caption("This section is designed for connected utility feeds, public datasets and validated meter imports. Current display uses simulated data when live sources are unavailable.")
    live = app_summary["live_feed"]
    st.dataframe(live, hide_index=True, use_container_width=True)

elif page == "UHBVN Consumer Help":
    st.title(_t("UHBVN Consumer Help"))
    st.caption("A plain-language guide to electricity bills, meter readings, payments and consumer services in Uttar Haryana.")
    st.info("PowerGuard is not connected to UHBVN's private billing system. It cannot retrieve personal bills, balances, payments or live readings. Use official UHBVN portals for account-specific services. Never enter OTPs, Aadhaar numbers or passwords here.")

    st.subheader("Official consumer services")
    links = [
        ("Pay / view bill", "https://epayment.uhbvn.org.in/b2cpaybill.aspx", "View the bill amount and pay through UHBVN."),
        ("Bill history", "https://epayment.uhbvn.org.in/b2cviewBillHistory.aspx", "Check previous bills using UHBVN's official consumer service."),
        ("Update consumer KYC", "https://epayment.uhbvn.org.in/updateKYC.aspx", "Use UHBVN's official process to update eligible consumer details and verify the registered mobile."),
        ("Trust Reading", "https://trustbill.uhbvn.org.in/", "Submit a self-reading if the billed reading appears incorrect and your account is eligible."),
        ("Submit meter reading", "https://trustbill.uhbvn.org.in/trustbased.aspx", "Official form for KWH/KVAH reading, OTP and meter photograph."),
        ("Track Trust Reading", "https://trustbill.uhbvn.org.in/CheckStatus.aspx", "Track by account number or case ID."),
        ("Payment history / receipt", "https://epayment.uhbvn.org.in/b2cViewReceiptList.aspx", "Look up payment records and receipts."),
        ("Complaints", "https://chs.uhbvn.org.in/", "Register and follow up on consumer complaints."),
    ]
    for i in range(0, len(links), 2):
        cols = st.columns(2)
        for col, item in zip(cols, links[i:i + 2]):
            with col:
                with st.container(border=True):
                    st.markdown("**" + item[0] + "**")
                    st.write(item[2])
                    st.markdown("<a href=\"" + item[1] + "\" target=\"_blank\" rel=\"noopener noreferrer\">Open official UHBVN service ↗</a>", unsafe_allow_html=True)

    st.divider()
    st.subheader(_t("How to understand your electricity bill"))
    terms = [
        ("Account / K. No.", "Your UHBVN consumer account identifier. Keep it private and use it only on official services."),
        ("Billing period", "The dates covered by this bill. Compare readings only for the same billing period."),
        ("Previous reading", "The meter reading recorded at the end of the previous billing cycle."),
        ("Current reading", "The reading recorded for the present billing cycle."),
        ("Units consumed (kWh)", "Usually current reading minus previous reading, multiplied by the meter multiplier. Special meter registers or corrections can change this calculation."),
        ("kVAh and maximum demand", "Some categories use kVAh energy or demand-related billing. Follow the unit and multiplier printed on your bill."),
        ("Fixed charges", "A tariff charge linked to category and sanctioned load/connection terms."),
        ("Energy charges", "Charges for units consumed under the applicable tariff slabs/rates."),
        ("Fuel / power purchase adjustment", "An approved adjustment may appear under labels such as FSA or other tariff components."),
        ("Electricity duty / taxes", "Applicable government levies shown as separate bill components."),
        ("Arrears / previous balance", "Amounts carried forward. Check official payment receipts if a previous payment is missing."),
        ("Rebate / subsidy / adjustment", "A credit applied only when the consumer meets the relevant scheme conditions."),
        ("Due date / late payment surcharge", "Pay by the due date printed on the bill. Applicable surcharge depends on current rules."),
    ]
    for title, detail in terms:
        with st.expander(title):
            st.write(detail)

    st.subheader(_t("Check your meter units"))
    st.write("For a basic cumulative kWh register:")
    st.latex(r"\text{Units consumed} = (\text{Current reading} - \text{Previous reading}) \times \text{Meter multiplier}")
    c1, c2, c3 = st.columns(3)
    with c1:
        prev = st.number_input("Previous reading (kWh)", min_value=0.0, value=0.0, key="uhbvn_prev")
    with c2:
        curr = st.number_input("Current reading (kWh)", min_value=0.0, value=0.0, key="uhbvn_curr")
    with c3:
        mult = st.number_input("Meter multiplier", min_value=0.0001, value=1.0, key="uhbvn_multiplier")
    if curr >= prev:
        st.metric("Indicative units consumed", f"{(curr - prev) * mult:,.2f} kWh")
    else:
        st.warning("Current reading is lower than previous. Check the register, dates, rollover or correction with UHBVN.")
    st.caption("This is an educational unit calculator, not an official bill calculator. It does not determine the payable amount.")

    st.subheader(_t("Trust Reading: what consumers should know"))
    st.write("UHBVN's Trust Reading portal describes eligibility for domestic, non-domestic and LT industrial consumers with load up to 20 kW and 10-digit account numbers. It requires OTP verification and a clear meter photograph. Confirm current eligibility and instructions on the official portal before submitting.")
    st.markdown("[Read UHBVN Trust Reading instructions] (https://trustbill.uhbvn.org.in/)")
    st.markdown("1. Match the meter number and consumer details on your bill.\n2. Note the correct kWh or kVAh register.\n3. Record the digits requested by the official form.\n4. Take a clear current photograph of the meter display.\n5. Submit only through UHBVN's official portal and keep the case ID/SMS.")

    st.subheader(_t("Common problems and what to do"))
    problems = [
        ("Wrong or unusually high bill", "Compare dates, readings, units and multiplier; check payment receipts; then raise a billing complaint."),
        ("Bill not received", "Check the official bill portal and register a bill-not-received complaint if needed."),
        ("Defective / stuck / fast / slow meter", "Request an official meter inspection. Do not open or interfere with the meter."),
        ("Burnt meter or no supply", "Report promptly using the official complaint channels."),
        ("Payment not reflected", "Keep the bank/UPI receipt or reference ID and contact UHBVN through its official portal."),
    ]
    for title, detail in problems:
        with st.expander(title):
            st.write(detail)

    st.subheader(_t("How to pay / fill in the online bill-payment form"))
    st.markdown("""
    1. Open the official [UHBVN bill payment portal](https://epayment.uhbvn.org.in/b2cpaybill.aspx).
    2. Read the page instructions and enter the consumer/account identifier exactly as printed on your bill in the field requested by the official portal.
    3. Check that the consumer name, bill month and payable amount shown by the official portal match your bill.
    4. Choose an available payment method shown by the portal and follow the bank/payment-provider steps.
    5. Wait for the success/receipt page. Save the receipt or transaction reference.
    6. If money is debited but the bill still appears unpaid, do not pay repeatedly immediately; keep the bank reference and contact UHBVN through its official complaint channel.
    """)
    st.warning("Never share your OTP, UPI PIN, card PIN, CVV or banking password with anyone or enter them into this prototype. Pay only on the official UHBVN portal.")

    st.subheader(_t("Prepare a complaint"))
    st.write("Choose the issue below to create a draft you can review and submit through UHBVN's official complaint channel. This tool does not submit the complaint for you.")
    issue_type = st.selectbox(
        "Complaint category",
        ["Wrong / high bill", "Bill not received", "Payment not updated", "Meter defective", "No electricity supply", "Meter burnt", "Other"],
        key="consumer_complaint_type",
    )
    complaint_name = st.text_input("Name (optional)", key="consumer_complaint_name")
    complaint_area = st.text_input("Area / locality (optional)", key="consumer_complaint_area")
    complaint_ref = st.text_input("Consumer number / account reference (optional; enter only on official form)", key="consumer_complaint_ref")
    complaint_details = st.text_area("Explain the issue (dates, bill month, readings or transaction reference; do not include OTP/PIN)", key="consumer_complaint_details")
    complaint_templates = {
        "Wrong / high bill": "I request verification of my electricity bill. Please check the billing period, previous and current meter readings, meter multiplier, units and applicable charges. Kindly arrange meter inspection if required and issue a corrected bill if an error is confirmed.",
        "Bill not received": "I have not received my electricity bill for the relevant billing period. Please verify the billing and registered delivery details and help me obtain the bill.",
        "Payment not updated": "I made a bill payment, but it is not reflected in my account. Please verify the transaction and update the payment status if received. I can provide the payment reference through the official channel.",
        "Meter defective": "I suspect that my electricity meter may be defective. Please register the complaint and arrange an official meter inspection.",
        "No electricity supply": "I am experiencing a power supply interruption at my location. Please register the no-supply complaint and provide an update.",
        "Meter burnt": "My electricity meter appears to be burnt or damaged. Please arrange an authorised inspection and replacement as per applicable procedure. I will not touch or open the meter.",
        "Other": "I request assistance with the electricity service issue described below. Please register the complaint, investigate and provide an update.",
    }
    draft = (
        f"Subject: {issue_type}\n\n"
        f"Name: {complaint_name or '[Enter name on official form]'}\n"
        f"Area: {complaint_area or '[Enter locality on official form]'}\n"
        f"Consumer reference: {complaint_ref or '[Enter securely on official portal]'}\n\n"
        f"{complaint_templates[issue_type]}\n\n"
        f"Details: {complaint_details or '[Add dates, bill month, readings or transaction reference]'}\n\n"
        "Please provide a complaint / docket number for future follow-up."
    )
    st.text_area("Complaint draft — review and copy", value=draft, height=230)
    st.download_button("Download complaint draft", draft.encode("utf-8"), "uhbvn_complaint_draft.txt", "text/plain")
    st.markdown("[Open official UHBVN complaint portal](https://chs.uhbvn.org.in/)")
    st.caption("Enter full account details only on the official UHBVN portal, not in this prototype. Attach copies of bills or payment receipts only when the official complaint process requests them.")

    st.subheader(_t("UHBVN consumer contact"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Helpline", "1912")
    c2.metric("Toll-free", "1800 180 1550")
    c3.metric("No-supply missed call", "9990231912")
    st.markdown("- WhatsApp chatbot: **9815961912**\n- Email: **1912@uhbvn.org.in**\n- SMS complaint number: **9152331912**")
    st.caption("Published complaint codes include NS (No Supply), MD (Meter Defective), MB (Meter Burnt), WB (Wrong Bill) and BNR (Bill Not Received). Check the current format on UHBVN's complaint portal.")
    st.markdown("[Open UHBVN complaint portal](https://chs.uhbvn.org.in/)")

    st.subheader(_t("Consumer rights and escalation"))
    st.write("If a complaint is not resolved through the normal channel, consumers may approach the Consumer Grievances Redressal Forum (CGRF) and, where applicable, the Electricity Ombudsman. Service timelines depend on the complaint type and current regulations.")
    st.markdown("[UHBVN Right to Service timelines (PDF)](https://www.uhbvn.org.in/staticContent/documents/RTS/Services_Right_To_Act.pdf)")
    st.markdown("[HERC CGRF information](https://www.herc.org.in/OmbudsmanContent/266_1_CGRF.aspx)")
    st.markdown("[UHBVN complaint-handling procedure (PDF)](https://www.uhbvn.org.in/staticContent/documents/Complaint%20Handling%20procedure.pdf)")

    st.subheader(_t("Tariff and public information"))
    st.markdown("- [UHBVN official website](https://www.uhbvn.org.in/)\n- [HERC website](https://herc.gov.in/)\n- [HERC regulations and tariff orders](https://herc.org.in/Regulation/1.aspx)")
    st.info("Tariff slabs, fixed charges, rebates and surcharges change by consumer category and effective date. This page does not hard-code a universal per-unit rate. Check the latest applicable UHBVN/HERC tariff order and the category printed on your bill.")
    st.caption("Sources checked 2 November 2026: UHBVN bill-payment portal, Trust Reading portal, payment-history page, complaint portal, Right to Service document and HERC consumer-grievance information. Informational guide; not an official UHBVN service.")

elif page == "India Monitoring":
    st.title(_t("India Monitoring"))
    st.caption("Public reference model for UHBVN, DHBVN and compatible future utilities.")
    utility = st.selectbox("Utility / region", [u["name"] for u in india_summary["utilities"]])
    util = next(u for u in india_summary["utilities"] if u["name"] == utility)

    c = st.columns(4)
    c[0].metric("Consumption", f"{util['consumption_gwh']:,.0f} GWh")
    c[1].metric("Losses", f"{util['loss_gwh']:,.0f} GWh")
    c[2].metric("Suspicious meters", f"{util['suspicious']:,.0f}")
    c[3].metric("System status", util["status"])

    st.subheader("Utility comparison")
    util_df = pd.DataFrame(india_summary["utilities"])
    fig = px.bar(
        util_df,
        x="name",
        y="loss_gwh",
        color="loss_gwh",
        title="Losses by Indian utility",
    )
    st.plotly_chart(plot_style(fig, 350), use_container_width=True)

    st.subheader("Regional monitoring")
    for item in india_summary["utilities"]:
        with st.expander(item["name"]):
            st.markdown(f"**Region:** {item['region']}  ")
            st.markdown(f"**Data source:** {item['source']}  ")
            st.markdown(f"**Connection status:** {item['connection']}  ")
            st.markdown(f"**Verified notes:** {item['notes']}  ")
            st.progress(float(item["risk_score"]), text=f"Risk score: {item['risk_score']}%")

elif page == "Theft Detection":
    st.title(_t("Theft Detection"))
    st.caption("Candidate anomalies are reviewed as potential issues, not proof of theft.")

    c = st.columns(4)
    c[0].metric("Readings analysed", f"{len(analysed):,}")
    c[1].metric("Flagged", f"{len(alerts)}", f"{len(alerts) / len(analysed) * 100:.1f}%", delta_color="off")
    c[2].metric("Rule + ML agree", int((alerts.detected_by == "Rule + ML").sum()))
    c[3].metric("Consumers involved", alerts.consumer_id.nunique())

    fig = px.scatter(
        analysed,
        x="expected_kwh",
        y="meter_kwh",
        color=analysed["flagged"].map({True: "Flagged", False: "Normal"}),
        color_discrete_map={"Flagged": RED, "Normal": BLUE},
        opacity=0.7,
        hover_data=["consumer_id", "day", "deviation_pct", "reason"],
        title="Expected vs recorded consumption",
    )
    mx = max(analysed.expected_kwh.max(), analysed.meter_kwh.max())
    fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", name="Meter = expected", line=dict(color=GREY, dash="dash"))
    fig.add_scatter(x=[0, mx], y=[0, mx * (1 - threshold / 100)], mode="lines", name=f"-{threshold}% threshold",
                    line=dict(color=ORANGE, dash="dot"))
    st.plotly_chart(plot_style(fig, 420), use_container_width=True)

    st.subheader("Detected readings")
    st.dataframe(
        alerts[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                "severity", "detected_by", "reason"]]
        .sort_values("deviation_pct", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

    if truth is not None and len(truth):
        with st.expander("Check against simulation scenarios"):
            m = analysed.merge(truth, on=["day", "consumer_id"], how="left")
            st.dataframe(
                m.groupby(m.kind.fillna("normal")).agg(
                    readings=("flagged", "size"), flagged=("flagged", "sum")
                ).assign(detection_rate=lambda d: (d.flagged / d.readings * 100).round(1)),
                use_container_width=True,
            )

elif page == "Data Centre":
    st.title(_t("Data Centre"))
    st.caption("CSV and public reference datasets are validated before analysis. Live utility integration is labelled and isolated.")

    st.subheader("Data quality overview")
    q = E.data_quality_snapshot(raw)
    c = st.columns(4)
    c[0].metric("Rows loaded", q["rows_total"])
    c[1].metric("Valid rows", q["rows_valid"])
    c[2].metric("Missing values", q["missing_cells"])
    c[3].metric("Duplicate rows", q["duplicate_rows"])

    st.subheader("Uploaded / loaded dataset")
    st.dataframe(raw.head(20), use_container_width=True)

    st.subheader("Data source / ingestion status")
    src = E.data_source_catalog()
    st.dataframe(pd.DataFrame(src), hide_index=True, use_container_width=True)

    if st.button("Save current readings and alerts to SQLite"):
        E.save_to_db(
            analysed[["day", "consumer_id", "category", "expected_kwh", "meter_kwh"]],
            alerts[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                    "severity", "detected_by", "reason"]],
            E.DB_PATH,
        )
        st.success(f"Saved to {E.DB_PATH.name}.")

elif page == "News Intelligence":
    st.title(_t("News Intelligence"))
    st.caption("Verified sources and public utility updates only. No fabricated incidents are published.")

    for item in news_items:
        with st.container():
            st.markdown(
                f"<div class='card'>"
                f"<div class='badge'>{item['verification']}</div><br>"
                f"<h4>{item['headline']}</h4>"
                f"<div class='small-muted'>{item['source']} · {item['date']} · {item['location']}</div><br>"
                f"{item['summary']}"
                f"</div>",
                unsafe_allow_html=True,
            )

elif page == "Reports":
    st.title(_t("Reports"))
    st.caption("Download suspicious records and data summaries. These are investigations, not legal proof of theft.")

    sev_sel = st.multiselect("Include severities", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    rep = alerts[alerts.severity.isin(sev_sel)]
    c = st.columns(3)
    c[0].metric("Rows in report", len(rep))
    c[1].metric("Consumers", rep.consumer_id.nunique())
    c[2].metric("Period", f"{pd.Timestamp(days[0]):%d %b} – {pd.Timestamp(days[-1]):%d %b}")

    if rep.empty:
        st.info("No export rows available with the current filters.")
    else:
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇ Download CSV", E.alerts_to_csv(rep), "anomaly_report.csv", "text/csv", use_container_width=True)
        d2.download_button(
            "⬇ Download PDF",
            E.alerts_to_pdf(rep, balance, {"threshold": threshold, "tech_loss": tech_loss}),
            "anomaly_report.pdf",
            "application/pdf",
            use_container_width=True,
        )
        d3.download_button("⬇ Full analysed data", analysed.to_csv(index=False).encode(), "analysed_readings.csv", "text/csv", use_container_width=True)

        st.dataframe(rep[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                          "severity", "detected_by", "reason"]], hide_index=True, use_container_width=True)

st.markdown("<hr style='border: 1px solid rgba(148,163,184,.15); margin-top: 1.5rem;'>", unsafe_allow_html=True)
