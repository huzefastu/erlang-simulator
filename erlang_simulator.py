import streamlit as st
import pandas as pd
import math
import io

st.sidebar.header("Paste Call Volume Table")

# Instructions for pasting
st.sidebar.markdown("*Copy 30-min interval data from your Excel and paste here. Use tab or comma separated format. Header row should be: Interval, Sunday, Monday, ..., Saturday*")

pasted_data = st.sidebar.text_area(
    "Paste your table data below (including header row):",
    height=300
)

if pasted_data.strip():
    try:
        # Try to read as CSV from the pasted text
        df = pd.read_csv(io.StringIO(pasted_data), sep=None, engine="python")
        st.subheader("Pasted Call Volume Table")
        st.dataframe(df)
    except Exception as e:
        st.error(f"Could not parse table data. Error: {e}")
else:
    st.warning("Paste your interval-level call volumes (with headers) above to proceed.")
#End Instructions for pasting
st.title("Contact Center Erlang Simulation")

st.sidebar.header("Simulation Parameters")
num_agents = st.sidebar.slider("Number of Agents", 1, 200, 50)
call_volume = st.sidebar.number_input("Hourly Call Volume", min_value=1, value=300)
aht = st.sidebar.number_input("Average Handling Time (seconds)", min_value=1, value=180)

st.write(f"**Number of Agents:** {num_agents}")
st.write(f"**Hourly Call Volume:** {call_volume}")
st.write(f"**Average Handling Time:** {aht} seconds")

# Agent Roster Automation (simple)
intervals = [f"{hour}:00-{hour+1}:00" for hour in range(9, 17)]  # 9am to 5pm, 8 intervals
agents_per_interval = num_agents // len(intervals)

# Build DataFrame for roster
roster = pd.DataFrame({
    "Interval": intervals,
    "Agents Assigned": [agents_per_interval] * len(intervals)
})

st.header("Automated Agent Roster")
st.dataframe(roster)

import math

def erlang_c(traffic_intensity, agents):
    # Calculate Erlang C probability of waiting
    traffic_power = traffic_intensity ** agents
    agents_fact = math.factorial(agents)
    
    # Calculate sum for C formula denominator
    sum_terms = sum([
        (traffic_intensity ** n) / math.factorial(n)
        for n in range(agents)
    ])
    
    erlangC = (traffic_power / agents_fact) * (agents / (agents - traffic_intensity))
    P_wait = erlangC / (sum_terms + erlangC)
    return P_wait

# Calculate traffic intensity (A): A = (Call Volume per hour * AHT in seconds) / 3600
traffic_intensity = (call_volume * aht) / 3600

# Erlang C probability that a call waits
if num_agents > traffic_intensity:
    prob_wait = erlang_c(traffic_intensity, num_agents)
    # Expected ASA (average speed of answer in seconds)
    asa = (prob_wait * aht) / (num_agents - traffic_intensity)
    # Example Service Level: % of calls answered within 20 seconds
    target_seconds = 20
    service_level = (1 - prob_wait * math.exp(-(num_agents - traffic_intensity) * (target_seconds / aht))) * 100
else:
    prob_wait = None
    asa = None
    service_level = None

# Output KPIs
st.header("Simulation KPIs")

if prob_wait is not None:
    st.write(f"**Probability Call Waits:** {prob_wait:.2%}")
    st.write(f"**Expected ASA (seconds):** {asa:.2f}")
    st.write(f"**Service Level (% within 20 sec):** {service_level:.2f}")
else:
    st.write("Not enough agents: traffic exceeds staffing. Increase agent count.")
