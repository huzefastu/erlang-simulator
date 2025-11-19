import streamlit as st
import pandas as pd
import math
import io

st.title("Contact Center Erlang Simulation")

# 1. SIMULATION MODE (main page)
sim_mode = st.radio(
    "Choose simulation mode:",
    [
        "Volume-based Requirement (Erlang)",
        "Hours-based Requirement (coverage)"
    ]
)
st.write(f"**Simulation mode selected:** {sim_mode}")

# 2. SIDEBAR: KPI, ASA, Scope, Shrinkage, Shift/Agent Rules
st.sidebar.header("KPI Setup")
kpi_options = [
    "Service Level (SLA)",
    "Abandon Rate",
    "Line Adherence",
    "Average Speed of Answer (ASA)"
]
selected_kpi = st.sidebar.selectbox("KPI for Simulation", kpi_options)

# Target for selected KPI
if selected_kpi == "Service Level (SLA)":
    target_kpi = st.sidebar.number_input("Target SLA (%)", value=80, min_value=0, max_value=100)
elif selected_kpi == "Abandon Rate":
    target_kpi = st.sidebar.number_input("Max Abandon Rate (%)", value=10, min_value=0, max_value=100)
elif selected_kpi == "Line Adherence":
    target_kpi = st.sidebar.number_input("Target Line Adherence (%)", value=90, min_value=0, max_value=100)
elif selected_kpi == "Average Speed of Answer (ASA)":
    target_kpi = st.sidebar.number_input("Max ASA (seconds)", value=20, min_value=1, max_value=1000)

# ASA target always present
asa_target = st.sidebar.number_input("ASA Target (seconds, always active)", value=20, min_value=1, max_value=1000)

# KPI Target Scope
target_scope = st.sidebar.selectbox(
    "Should KPI be met per:",
    ["Interval", "Day", "Week"]
)

# Shrinkage Setup
st.sidebar.header("Shrinkage Setup")
in_office_shrinkage = st.sidebar.number_input(
    "In-office Shrinkage (%) (breaks, coaching, meetings…)", value=20, min_value=0, max_value=100
)
out_office_shrinkage = st.sidebar.number_input(
    "Out-of-office Shrinkage (%) (leaves, absences, holidays…)", value=10, min_value=0, max_value=100
)

# Shift/Agent Rules Section
st.sidebar.header("Shift & Agent Rules")
num_shifts = st.sidebar.number_input("Number of Different Shifts", value=3, min_value=1, max_value=10)
max_hours_per_agent = st.sidebar.number_input("Max Hours per Agent per Day", min_value=1, max_value=12, value=8)
min_shift_gap = st.sidebar.number_input("Min Gap Between Shifts (hours)", min_value=0, max_value=24, value=10)
working_days_per_week = st.sidebar.number_input("Agent Working Days per Week", min_value=1, max_value=7, value=5)
min_shift_length = st.sidebar.number_input("Minimum Shift Length (hours)", min_value=1, max_value=12, value=4)
max_shift_length = st.sidebar.number_input("Maximum Shift Length (hours)", min_value=1, max_value=12, value=8)

# Show sidebar settings summary in main area
st.markdown(
    f"""**Sidebar KPI & Shrinkage & Shift/Agent Rules Setup**:  
- **KPI:** {selected_kpi} (Target: {target_kpi})
- **ASA Target (seconds):** {asa_target}
- **KPI Target Scope:** {target_scope}
- **In-office Shrinkage:** {in_office_shrinkage}%  
- **Out-of-office Shrinkage:** {out_office_shrinkage}%  
- **Number of Different Shifts:** {num_shifts}  
- **Max Hours/Agent/Day:** {max_hours_per_agent}  
- **Min Gap Between Shifts:** {min_shift_gap} hours  
- **Working Days per Week:** {working_days_per_week}  
- **Min/Max Shift Length:** {min_shift_length}-{max_shift_length} hours  
"""
)

# 3. MAIN PAGE: Paste Table Input by Mode
if sim_mode == "Volume-based Requirement (Erlang)":
    st.header("Paste Call Volume Table")
    st.markdown("*Copy 30-min interval data from Excel and paste here. Use tab or comma separated format. Header row should be: Interval, Sunday, Monday, ..., Saturday*")
    pasted_data = st.text_area(
        "Paste your table data below (include header):",
        height=300
    )

    if pasted_data.strip():
        try:
            df = pd.read_csv(io.StringIO(pasted_data), sep=None, engine="python")
            st.subheader("Pasted Call Volume Table")
            st.dataframe(df)
            # Further simulation/evaluation logic can go here...

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
    else:
        st.info("Paste your interval-level call volumes (with headers) above to proceed.")

elif sim_mode == "Hours-based Requirement (coverage)":
    st.header("Paste Table of Hours Required per Interval")
    st.markdown("*Copy hours required for each 30-min interval, by day. Same format as volume table, header row: Interval, Sunday, Monday, ..., Saturday*")
    pasted_hours = st.text_area(
        "Paste your table data below (include header):",
        height=300
    )

    if pasted_hours.strip():
        try:
            hrs_df = pd.read_csv(io.StringIO(pasted_hours), sep=None, engine="python")
            st.subheader("Pasted Hours Requirement Table")
            st.dataframe(hrs_df)
            # Further simulation/evaluation logic can go here...

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
    else:
        st.info("Paste your interval-level hours required (with headers) above to proceed.")
