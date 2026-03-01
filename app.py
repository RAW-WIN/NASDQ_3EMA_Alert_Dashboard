import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

# ---------------------------------------------------
# Page Config
# ---------------------------------------------------
st.set_page_config(page_title="NASDQ 3EMA Alert Dashboard", layout="wide")
st.title("📈 24/7 Moving Average Alert Dashboard")

# ---------------------------------------------------
# Auto Refresh Every 5 Minutes
# ---------------------------------------------------
st_autorefresh(interval=300000, key="auto_refresh")

# ---------------------------------------------------
# Session State
# ---------------------------------------------------
if "alerted_signals" not in st.session_state:
    st.session_state.alerted_signals = {}

# ---------------------------------------------------
# Sidebar Settings
# ---------------------------------------------------
st.sidebar.header("Stock Scanner Settings")

symbol_input = st.sidebar.text_input(
    "Enter stock symbols (comma separated)",
    value="AAPL,MSFT,NVDA,TSLA,AMZN"
)

period = st.sidebar.selectbox(
    "Select historical period",
    ["3mo", "6mo", "1y", "2y", "5y"]
)

enable_email = st.sidebar.checkbox("Enable Email Alerts")

symbols = [s.strip().upper() for s in symbol_input.split(",")]

# ---------------------------------------------------
# Sector Mapping (Editable)
# ---------------------------------------------------
sector_map = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary"
}

# ---------------------------------------------------
# Email Configuration
# ---------------------------------------------------
try:
    sender_email = st.secrets["SENDER_EMAIL"]
    sender_password = st.secrets["SENDER_PASSWORD"]
    recipient_email = st.secrets["RECIPIENT_EMAIL"]
except Exception:
    sender_email = ""
    sender_password = ""
    recipient_email = ""

# ---------------------------------------------------
# Email Functions
# ---------------------------------------------------
def send_email_alert(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        return False


def send_test_email():
    try:
        msg = MIMEText("✅ Your NASDAQ 3 EMA Alert system is working correctly.")
        msg["Subject"] = f"Test Alert - {datetime.now()}"
        msg["From"] = sender_email
        msg["To"] = recipient_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()

        st.success("✅ Test email sent successfully!")
    except Exception as e:
        st.error(f"❌ Email failed: {e}")

# ---------------------------------------------------
# Fetch Stock Data
# ---------------------------------------------------
@st.cache_data
def fetch_stock_data(symbol, period):

    df = yf.download(symbol, period=period, progress=False)

    if df.empty or len(df) < 50:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()

    df["Buy_Signal"] = (
        (df["MA10"] > df["MA20"]) &
        (df["MA10"].shift(1) <= df["MA20"].shift(1))
    )

    df["Sell_Signal"] = (
        (df["MA50"] > df["MA10"]) &
        (df["MA50"].shift(1) <= df["MA10"].shift(1))
    )

    last_row = df.iloc[-1]

    return {
        "Symbol": symbol,
        "Buy Today": bool(last_row["Buy_Signal"]),
        "Sell Today": bool(last_row["Sell_Signal"]),
        "Last Close": float(last_row["Close"]),
        "Data": df
    }

# ---------------------------------------------------
# Run Scan
# ---------------------------------------------------
results = []
recent_signals = []

lookback_days = 10
cutoff_date = datetime.now() - timedelta(days=lookback_days)

for s in symbols:
    result = fetch_stock_data(s, period)
    if result:
        results.append(result)

        df = result["Data"]

        recent = df[
            (df["Buy_Signal"] | df["Sell_Signal"]) &
            (df.index >= cutoff_date)
        ]

        for idx, row in recent.iterrows():
            signal_type = "BUY" if row["Buy_Signal"] else "SELL"
            days_ago = (datetime.now() - idx).days

            recent_signals.append({
                "Ticker": s,
                "Sector": sector_map.get(s, "Unknown"),
                "Signal": signal_type,
                "Signal Date": idx.date(),
                "Days Ago": days_ago
            })

# ---------------------------------------------------
# Display Results
# ---------------------------------------------------
st.subheader("Scan Results")

if results:
    df_results = pd.DataFrame(results).drop(columns=["Data"])
    st.dataframe(df_results, use_container_width=True)
else:
    st.warning("No valid data returned.")

# ---------------------------------------------------
# Recent Signal Table with Filter + Sector Grouping
# ---------------------------------------------------
st.divider()
st.subheader("📊 Recent Buy/Sell Signals (Last 10 Days)")

signal_df = pd.DataFrame(recent_signals)

if not signal_df.empty:

    filter_option = st.selectbox(
        "Filter by Signal Type",
        ["Both", "BUY", "SELL"],
        key="signal_filter"
    )

    if filter_option != "Both":
        filtered_df = signal_df[signal_df["Signal"] == filter_option]
    else:
        filtered_df = signal_df.copy()

    # Sector Summary
    st.markdown("### 📈 Signals by Sector")

    sector_summary = (
        filtered_df.groupby(["Sector", "Signal"])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    st.dataframe(sector_summary, use_container_width=True)

    # Detailed Table
    st.markdown("### 📋 Signal Details")
    filtered_df = filtered_df.sort_values("Signal Date", ascending=False)
    st.dataframe(filtered_df, use_container_width=True)

    # Export CSV
    csv = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📥 Export to CSV",
        data=csv,
        file_name="recent_ema_signals.csv",
        mime="text/csv",
        key="export_csv_button"
    )

else:
    st.info("No buy or sell signals in the past 10 days.")

# ---------------------------------------------------
# Email Test Section
# ---------------------------------------------------
st.divider()
st.subheader("📧 Email Test")

if st.button("Send Test Email", key="test_email_button"):
    send_test_email()



