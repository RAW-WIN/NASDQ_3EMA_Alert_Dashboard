
import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_autorefresh import st_autorefresh
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import streamlit as st


def send_test_email():
    try:
        msg = MIMEText("✅ Your NASDAQ 3 EMA Alert system is working correctly.")
        msg["Subject"] = "Test Alert - NASDAQ EMA Dashboard"
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

# Button
if st.button("Send Test Email"):
    send_test_email()

# ---------------------------------------------------
# Page Config
# ---------------------------------------------------
st.set_page_config(page_title="Stock MA Alert Dashboard", layout="wide")

st.title("📈 24/7 Moving Average Alert Dashboard")

# ---------------------------------------------------
# Auto Refresh Every 5 Minutes
# ---------------------------------------------------
st_autorefresh(interval=300000, key="auto_refresh")

# ---------------------------------------------------
# Session State for Duplicate Alert Prevention
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
# Email Configuration (Cloud + Local Safe Version)
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
# Email Function
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

# ---------------------------------------------------
# Fetch & Analyze Stock Data
# ---------------------------------------------------
@st.cache_data
def fetch_stock_data(symbol, period):

    df = yf.download(symbol, period=period, progress=False)

    if df.empty or len(df) < 50:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Moving Averages
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()

    # Buy Signal: MA10 crosses above MA20
    df["Buy_Signal"] = (
        (df["MA10"] > df["MA20"]) &
        (df["MA10"].shift(1) <= df["MA20"].shift(1))
    )

    # Sell Signal: MA50 crosses above MA10
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
# Run Scan Automatically
# ---------------------------------------------------
results = []
for s in symbols:
    result = fetch_stock_data(s, period)
    if result:
        results.append(result)

# ---------------------------------------------------
# Display Scan Results
# ---------------------------------------------------
st.subheader("Scan Results")

if not results:
    st.warning("No valid data returned.")
else:
    df_results = pd.DataFrame(results).drop(columns=["Data"])
    st.dataframe(df_results, use_container_width=True)

# ---------------------------------------------------
# Email Alert Logic (Price > $50 Only)
# ---------------------------------------------------
if enable_email and sender_email and sender_password and recipient_email:

    for r in results:
        symbol = r["Symbol"]
        price = r["Last Close"]
        buy = r["Buy Today"]
        sell = r["Sell Today"]

        if price > 50:

            signal_key = f"{symbol}_{buy}_{sell}"

            if signal_key not in st.session_state.alerted_signals:

                if buy:
                    subject = f"🚀 BUY ALERT: {symbol}"
                    body = f"""
Buy Signal Detected!

Stock: {symbol}
Price: ${price:.2f}

MA10 crossed above MA20.
                    """
                    if send_email_alert(subject, body):
                        st.session_state.alerted_signals[signal_key] = True

                elif sell:
                    subject = f"🔻 SELL ALERT: {symbol}"
                    body = f"""
Sell Signal Detected!

Stock: {symbol}
Price: ${price:.2f}

MA50 crossed above MA10.
                    """
                    if send_email_alert(subject, body):
                        st.session_state.alerted_signals[signal_key] = True

# ---------------------------------------------------
# Professional Chart Section
# ---------------------------------------------------
if results:

    selected_symbol = st.selectbox(
        "Select stock to view chart",
        [r["Symbol"] for r in results]
    )

    selected_data = next(r for r in results if r["Symbol"] == selected_symbol)["Data"]

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(selected_data.index, selected_data["Close"], label="Close", linewidth=2)
    ax.plot(selected_data.index, selected_data["MA10"], label="MA10 (10-day)", linewidth=1.5)
    ax.plot(selected_data.index, selected_data["MA20"], label="MA20 (20-day)", linewidth=1.5)
    ax.plot(selected_data.index, selected_data["MA50"], label="MA50 (50-day)", linewidth=1.5)

    buy_signals = selected_data[selected_data["Buy_Signal"]]
    sell_signals = selected_data[selected_data["Sell_Signal"]]

    ax.scatter(buy_signals.index, buy_signals["Close"],
               marker="^", s=120, label="Buy Signal")

    ax.scatter(sell_signals.index, sell_signals["Close"],
               marker="v", s=120, label="Sell Signal")

    ax.set_title(f"{selected_symbol} Price & MA Signals",
                 fontsize=16, fontweight="bold")

    ax.set_xlabel("Date")
    ax.set_ylabel("Price (USD)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper left")

    plt.xticks(rotation=45)
    plt.tight_layout()


    st.pyplot(fig)

st.divider()
st.subheader("📧 Email Test")

if st.button("Send Test Email", key="test_email_button"):
    send_test_email()
