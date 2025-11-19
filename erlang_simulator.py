import streamlit as st
import pandas as pd
import math
import io

st.title("Contact Center Erlang Simulation")

# 1. SIMULATION MODE FIRST
sim_mode = st.radio(
    "Choose simulation mode:",
    [
        "Volume-based Requirement (Erlang)",
        "Hours-based Requirement (coverage)"
    ]
)
st.write(f"**Simulation mode selected:** {sim_mode}")

# 2. Main Inputs and Logic Change Based on Mode

if sim_mode == "Volume-based Requirement (Erlang)":
    # --- VOLUME MODE: Focus on interval call volumes ---
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

            # KPI selection
            st.header("Select KPI for Simulation")
            kpi_options = [
                "Service Level (SLA)",
                "Abandon Rate",
                "Line Adherence",
                "Average Speed of Answer (ASA)"
            ]
            selected_kpi = st.selectbox("Which KPI should the simulation focus on?", kpi_options)
            st.write(f"**Current target KPI:** {selected_kpi}")

            # Basic simulation parameters (single test interval for demo)
            st.sidebar.header("Simulation Parameters")
            num_agents = st.sidebar.slider("Number of Agents", 1, 200, 50)
            call_volume = st.sidebar.number_input("Hourly Call Volume", min_value=1, value=300)
            aht = st.sidebar.number_input("Average Handling Time (seconds)", min_value=1, value=180)
            st.write(f"**Number of Agents:** {num_agents}")
            st.write(f"**Hourly Call Volume:** {call_volume}")
            st.write(f"**Average Handling Time:** {aht} seconds")

            # Erlang C simulation (single test interval for now)
            def erlang_c(traffic_intensity, agents):
                traffic_power = traffic_intensity ** agents
                agents_fact = math.factorial(agents)
                sum_terms = sum([
                    (traffic_intensity ** n) / math.factorial(n)
                    for n in range(agents)
                ])
                erlangC = (traffic_power / agents_fact) * (agents / (agents - traffic_intensity))
                P_wait = erlangC / (sum_terms + erlangC)
                return P_wait

            traffic_intensity = (call_volume * aht) / 3600
            if num_agents > traffic_intensity:
                prob_wait = erlang_c(traffic_intensity, num_agents)
                asa = (prob_wait * aht) / (num_agents - traffic_intensity)
                target_seconds = 20
                service_level = (1 - prob_wait * math.exp(-(num_agents - traffic_intensity) * (target_seconds / aht))) * 100
            else:
                prob_wait = None
                asa = None
                service_level = None

            st.header("Simulation KPIs")
            if prob_wait is not None:
                st.write(f"**Probability Call Waits:** {prob_wait:.2%}")
                st.write(f"**Expected ASA (seconds):** {asa:.2f}")
                st.write(f"**Service Level (% within 20 sec):** {service_level:.2f}")
            else:
                st.write("Not enough agents: traffic exceeds staffing. Increase agent count.")

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
    else:
        st.info("Paste your interval-level call volumes (with headers) above to proceed.")

elif sim_mode == "Hours-based Requirement (coverage)":
    # --- HOURS MODE: Focus on hours required per interval ---
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

            # Example additional parameters (customize)
            st.sidebar.header("Coverage Simulation Parameters")
            num_agents = st.sidebar.slider("Number of Agents", 1, 200, 50)
            max_hours_per_agent = st.sidebar.number_input("Max Hours per Agent per Day", min_value=1, max_value=12, value=8)
            min_shift_length = st.sidebar.number_input("Minimum Shift Length", min_value=1, max_value=8, value=4)
            max_shift_length = st.sidebar.number_input("Maximum Shift Length", min_value=1, max_value=12, value=8)
            st.write(f"**Number of Agents:** {num_agents}")
            st.write(f"**Max Hours per Agent per Day:** {max_hours_per_agent}")
            st.write(f"**Shift length range:** {min_shift_length} - {max_shift_length} hours")

            # For future: Calculate coverage & display results

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
    else:
        st.info("Paste your interval-level hours required (with headers) above to proceed.")

