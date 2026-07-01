import streamlit as st
import pandas as pd
import requests

# --- Web App UI Setup ---
st.set_page_config(page_title="Athlete Profile", layout="wide")

# Sidebar for Credentials (Makes it shareable!)
st.sidebar.header("🔑 Your Intervals.icu Credentials")
st.sidebar.markdown("Find these in your Intervals.icu **Settings > Developer Settings**.")
ATHLETE_ID = st.sidebar.text_input("Athlete ID (e.g., i12345)")
API_KEY = st.sidebar.text_input("API Key", type="password")

BASE_URL = "https://intervals.icu/api/v1"

@st.cache_data(show_spinner=False)
def fetch_data(athlete_id, api_key):
    """Fetches athlete profile and activity data from Intervals.icu"""
    auth = requests.auth.HTTPBasicAuth('API_KEY', api_key)
    
    profile_url = f"{BASE_URL}/athlete/{athlete_id}"
    profile_resp = requests.get(profile_url, auth=auth)
    name = profile_resp.json().get('name', 'Athlete') if profile_resp.status_code == 200 else 'Unknown Athlete'
    
    activities_url = f"{BASE_URL}/athlete/{athlete_id}/activities"
    params = {"fields": "id,start_date_local,type,distance,moving_time,average_heartrate,icu_ctl,icu_atl"}
    act_resp = requests.get(activities_url, auth=auth, params=params)
    
    df = pd.DataFrame(act_resp.json()) if act_resp.status_code == 200 else pd.DataFrame()
    return name, df

def process_data(df):
    """Processes raw data into yearly summaries and PRs"""
    if df.empty:
        return df, None, None
        
    df['date'] = pd.to_datetime(df['start_date_local'])
    df['year'] = df['date'].dt.year
    df['distance_km'] = df['distance'] / 1000.0
    df['moving_time_min'] = df['moving_time'] / 60.0
    df['pace_min_km'] = df['moving_time_min'] / df['distance_km']
    
    runs = df[df['type'] == 'Run'].copy()
    
    # 1. Yearly Summary
    yearly = runs.groupby('year').agg(
        Total_Distance_km=('distance_km', 'sum'),
        Total_Time_hr=('moving_time_min', lambda x: x.sum() / 60.0),
        Avg_Pace_min_km=('pace_min_km', 'mean'),
        Avg_HR=('average_heartrate', 'mean')
    ).round(2).reset_index()

    yearly['Avg_Pace_min_km'] = yearly['Avg_Pace_min_km'].apply(
        lambda x: f"{int(x)}:{int((x % 1) * 60):02d}" if pd.notnull(x) else ""
    )

    # 2. CTL & ATL Stats
    load_stats = {
        "CTL": {"Max": round(df['icu_ctl'].max(), 1), "Avg": round(df['icu_ctl'].mean(), 1)},
        "ATL": {"Max": round(df['icu_atl'].max(), 1), "Avg": round(df['icu_atl'].mean(), 1)}
    }
    
    # 3. Best Results by Standard Distances
    distances = {"1500m": [1.4, 1.6], "5K": [4.8, 5.2], "10K": [9.8, 10.2], "Half Marathon": [20.9, 21.3], "Marathon": [41.9, 42.5]}
    prs = []
    for d_name, bounds in distances.items():
        matches = runs[(runs['distance_km'] >= bounds[0]) & (runs['distance_km'] <= bounds[1])]
        if not matches.empty:
            best = matches.loc[matches['moving_time'].idxmin()]
            pace = best['pace_min_km']
            pace_str = f"{int(pace)}:{int((pace % 1) * 60):02d}"
            prs.append({"Distance": d_name, "Best Time (Mins)": round(best['moving_time_min'], 1), "Avg Pace": pace_str, "Date": best['date'].strftime('%Y-%m-%d')})
            
    return yearly, load_stats, pd.DataFrame(prs)

# --- Main App Logic ---
st.title("🏃‍♂️ Intervals.icu Athlete Profile")

# Stop the app from running further if credentials are not entered yet
if not ATHLETE_ID or not API_KEY:
    st.info("Please enter your Athlete ID and API Key in the sidebar to load your dashboard.")
    st.stop()

with st.spinner("Fetching data from Intervals.icu..."):
    name, raw_df = fetch_data(ATHLETE_ID, API_KEY)

if raw_df.empty:
    st.error("Could not fetch data. Please check that your Athlete ID and API Key are correct.")
else:
    yearly_df, load_stats, prs_df = process_data(raw_df)

    st.subheader(f"Data for: {name}")
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("All-Time Max CTL", load_stats["CTL"]["Max"])
    col2.metric("Average CTL", load_stats["CTL"]["Avg"])
    col3.metric("All-Time Max ATL", load_stats["ATL"]["Max"])
    col4.metric("Average ATL", load_stats["ATL"]["Avg"])
    
    st.markdown("---")
    st.subheader("📅 Yearly Run Aggregates")
    st.dataframe(yearly_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Best Results by Distance")
    if not prs_df.empty:
        st.dataframe(prs_df, use_container_width=True, hide_index=True)
    else:
        st.info("No standard race distances found in the data history.")
