import streamlit as st
import pandas as pd

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
