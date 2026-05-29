import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import io
from datetime import datetime, timezone
from supabase import create_client
import plotly.express as px
import pytz

# --- Supabase client ---
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# --- Data fetching every 5min -- 
@st.cache_data(ttl=300)
def fetch_and_save():
    supabase = get_supabase()

    # Scrape live data from WA Health
    url = "https://www.health.wa.gov.au/Reports-and-publications/Emergency-Department-activity/Data?report=ed_activity_now"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    df = pd.read_html(io.StringIO(str(table)))[0]

    # Rename to match Supabase column names exactly
    df.columns = ["hospital", "avg_wait_triage4_mins", "pt_waiting_to_be_seen", "total_in_ed"]

    # Extract timestamp from table title
    title_text = soup.find(string=lambda t: t and "Preview of Emergency Department" in t)

    try:
        time_str = title_text.split("at ")[-1].strip()
        timestamp = datetime.strptime(time_str, "%A, %d %B %Y %I:%M %p")
        perth_tz = pytz.timezone("Australia/Perth")
        timestamp = perth_tz.localize(timestamp)
        df["timestamp"] = timestamp.isoformat()
    except:
        # Fallback to current Perth time if parsing fails
        perth_tz = pytz.timezone("Australia/Perth")
        df["timestamp"] = datetime.now(perth_tz).isoformat()

    # Save to Supabase
    rows = df.to_dict(orient="records")
    try:
        supabase.table("ed_history").insert(rows).execute()
        st.success(f"✅ Inserted {len(rows)} rows at {df['timestamp'].iloc[0]}")
    except Exception as e:
        st.warning(f"Could not insert new data: {e}")

    # Load last 24 hours from Supabase
    cutoff = (datetime.now(timezone.utc) - pd.Timedelta(hours=24)).isoformat()
    result = supabase.table("ed_history").select("*").gte("timestamp", cutoff).execute()
    history = pd.DataFrame(result.data)
    
    if not history.empty:
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
