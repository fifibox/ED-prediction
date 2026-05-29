import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import io
import os
from datetime import datetime
import plotly.express as px

HISTORY_FILE = "ed_history.csv"

@st.cache_data(ttl=300)
def fetch_and_save():
    url = "https://www.health.wa.gov.au/Reports-and-publications/Emergency-Department-activity/Data?report=ed_activity_now"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")

    df = pd.read_html(io.StringIO(str(table)))[0]
    df.columns = ["Hospital", "Avg_Wait_Triage4_mins", "Waiting_to_be_Seen", "Total_in_ED"]
    df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Append to history csv file
    if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 0:
        history = pd.read_csv(HISTORY_FILE)
        history = pd.concat([history, df], ignore_index=True)
    else:
        history = df

    # Keep only last 24 hours
    history["Timestamp"] = pd.to_datetime(history["Timestamp"])
    cutoff = pd.Timestamp.now() - pd.Timedelta(hours=24)
    history = history[history["Timestamp"] > cutoff]

    history.to_csv(HISTORY_FILE, index=False)
    return history


# --- Streamlit App ---
st.title("🚨 WA ED — 24 Hour Wait Time Trend")

history = fetch_and_save()

if len(history["Timestamp"].unique()) < 2:
    st.warning("⏳ Not enough data yet — the chart will fill in as data is collected every 5 minutes. Leave the app running!")
else:
    # Hospital filter
    hospitals = sorted(history["Hospital"].unique())
    selected = st.multiselect("Select hospitals", hospitals, default=hospitals)

    filtered = history[history["Hospital"].isin(selected)]

    fig = px.line(
        filtered,
        x="Timestamp",
        y="Avg_Wait_Triage4_mins",
        color="Hospital",
        markers=True,
        labels={"Avg_Wait_Triage4_mins": "Avg Wait (mins)", "Timestamp": "Time"},
        title="Triage 4 Average Wait Time — Last 24 Hours"
    )
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Wait Time (minutes)",
        legend_title="Hospital",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"🔄 Auto-refreshes every 5 minutes | Data saved to `{HISTORY_FILE}`")