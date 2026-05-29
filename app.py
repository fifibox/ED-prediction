import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import io
from datetime import datetime, timezone
from supabase import create_client

# --- Supabase client ---
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

@st.cache_data(ttl=300)
def fetch_and_save():
    supabase = get_supabase()

    # Scrape live data
    url = "https://www.health.wa.gov.au/Reports-and-publications/Emergency-Department-activity/Data?report=ed_activity_now"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    df = pd.read_html(io.StringIO(str(table)))[0]
    df.columns = ["Hospital", "Avg_Wait_Triage4_mins", "Waiting_to_be_Seen", "Total_in_ED"]
    df["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Save to Supabase
    rows = df.rename(columns={
        "hospital": "hospital",
        "avg_wait_triage4_mins": "avg_wait_triage4_mins",
        "pt_waiting_to_be_seen": "pt_waiting_to_be_seen",
        "total_in_ed": "total_in_ed",
        "timestamp": "timestamp"
    }).to_dict(orient="records")
    supabase.table("ed_history").insert(rows).execute()

    # Load last 24 hours
    cutoff = (datetime.now(timezone.utc) - pd.Timedelta(hours=24)).isoformat()
    result = supabase.table("ed_history").select("*").gte("timestamp", cutoff).execute()
    history = pd.DataFrame(result.data)
    history["timestamp"] = pd.to_datetime(history["timestamp"])

    return history


# --- Streamlit App ---
st.title("🚨 WA ED — 24 Hour Wait Time Trend")

history = fetch_and_save()

if history.empty or len(history["timestamp"].unique()) < 2:
    st.warning("⏳ Not enough data yet — check back in a few minutes!")
else:
    hospitals = sorted(history["hospital"].unique())
    selected = st.multiselect("Select hospitals", hospitals, default=hospitals)
    filtered = history[history["hospital"].isin(selected)]

    import plotly.express as px
    fig = px.line(
        filtered,
        x="timestamp",
        y="avg_wait_triage4_mins",
        color="hospital",
        markers=True,
        labels={"avg_wait_triage4_mins": "Avg Wait (mins)", "timestamp": "Time"},
        title="Triage 4 Average Wait Time — Last 24 Hours"
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

st.caption("🔄 Auto-refreshes every 5 minutes")