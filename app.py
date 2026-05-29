import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import io
from datetime import datetime, timezone
from supabase import create_client
import plotly.express as px

# --- Supabase client ---
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

@st.cache_data(ttl=300)
def fetch_and_save():
    supabase = get_supabase()

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

