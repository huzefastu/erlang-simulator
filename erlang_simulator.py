import streamlit as st
import pandas as pd
import math
import io

st.title("Contact Center Erlang Simulation")

# ---- MODE SELECTION ----
sim_mode = st.radio(
    "Choose simulation mode:",
    [
        "Volume-based Requirement (Erlang)",
        "Hours-based Requirement (coverage)"
    ]
)
st.write(f"**Simulation mode selected:** {sim_mode}")

# ---- SIDEBAR CONTROLS ----
st.sidebar.header("KPI Setup")
kpi_options = [
    "Service Level (SLA)",
    "Abandon Rate",
    "Line Adherence",
    "Average Speed of Answer (ASA)"
]
selected_kpi = st.sidebar.selectbox("KPI for Simulation", kpi_options)

if selected_kpi == "Service Level (SLA)":
    target_kpi = st.sidebar.number_input("Target SLA (%)", value=80, min_value=0, max_value=100)
elif selected_kpi == "Abandon Rate":
    target_kpi = st.sidebar.number_input("Max Abandon Rate (%)", value=10, min_value=0, max_value=100)
elif selected_kpi == "Line Adherence":
    target_kpi = st.sidebar.number_input("Target Line Adherence (%)", value=100, min_value=0, max_value=100)
elif selected_kpi == "Average Speed of Answer (ASA)":
    target_kpi = st.sidebar.number_input("Max ASA (seconds)", value=20, min_value=1, max_value=1000)

asa_target = st.sidebar.number_input("ASA Target (seconds, always active)", value=20, min_value=1, max_value=1000)
target_scope = st.sidebar.selectbox("Should KPI be met per:", ["Interval", "Day", "Week"])

# Abandon Rate patience input
if selected_kpi == "Abandon Rate":
    st.sidebar.markdown("**Abandon Rate Simulation requires estimated caller patience (seconds):**")
    patience = st.sidebar.number_input("Average Caller Patience (seconds)", value=30, min_value=1, max_value=600)
else:
    patience = st.sidebar.number_input("Average Caller Patience (seconds)", value=30, min_value=1, max_value=600, disabled=True)

st.sidebar.header("Shrinkage Setup")
in_office_shrinkage = st.sidebar.number_input("In-office Shrinkage (%) (breaks, coaching, meetings…)", value=20, min_value=0, max_value=100)
out_office_shrinkage = st.sidebar.number_input("Out-of-office Shrinkage (%) (leaves, absences, holidays…)", value=10, min_value=0, max_value=100)

st.sidebar.header("Shift & Agent Rules")
num_shifts = st.sidebar.number_input("Number of Different Shifts", value=3, min_value=1, max_value=10)
max_hours_per_agent = st.sidebar.number_input("Max Hours per Agent per Day", min_value=1, max_value=12, value=8)
min_shift_gap = st.sidebar.number_input("Min Gap Between Shifts (hours)", min_value=0, max_value=24, value=10)
working_days_per_week = st.sidebar.number_input("Agent Working Days per Week", min_value=1, max_value=7, value=5)
min_shift_length = st.sidebar.number_input("Minimum Shift Length (hours)", min_value=1, max_value=12, value=4)
max_shift_length = st.sidebar.number_input("Maximum Shift Length (hours)", min_value=1, max_value=12, value=8)

st.markdown(
    f"""**Sidebar KPI & Shrinkage & Shift/Agent Rules Setup**:  
- **KPI:** {selected_kpi} (Target: {target_kpi})
- **ASA Target (seconds):** {asa_target}
- **KPI Target Scope:** {target_scope}
- **Average Caller Patience (seconds):** {patience}
- **In-office Shrinkage:** {in_office_shrinkage}%  
- **Out-of-office Shrinkage:** {out_office_shrinkage}%  
- **Number of Different Shifts:** {num_shifts}  
- **Max Hours/Agent/Day:** {max_hours_per_agent}  
- **Min Gap Between Shifts:** {min_shift_gap} hours  
- **Working Days per Week:** {working_days_per_week}  
- **Min/Max Shift Length:** {min_shift_length}-{max_shift_length} hours  
"""
)

if sim_mode == "Volume-based Requirement (Erlang)":
    st.header("Paste Call Volume Table")
    st.markdown("*Copy 30-min interval data from Excel and paste here. Use tab or comma separated format. Header row should be: Interval, Sunday, Monday, ..., Saturday*")
    pasted_data = st.text_area("Paste your table data below (include header):", height=300)

    if pasted_data.strip():
        try:
            df = pd.read_csv(io.StringIO(pasted_data), sep=None, engine="python")
            st.subheader("Pasted Call Volume Table")
            st.dataframe(df)

            if 'Interval' not in df.columns:
                st.error(f"Your pasted data does not have a column labeled 'Interval'. Columns found: {list(df.columns)}")
                st.stop()

            days = [col for col in df.columns if col.lower() != 'interval']
            selected_day = st.selectbox("Select Day to Simulate", days)

            def erlang_c(traffic_intensity, agents):
                if agents <= traffic_intensity:
                    return None
                traffic_power = traffic_intensity ** agents
                agents_fact = math.factorial(agents)
                sum_terms = sum([
                    (traffic_intensity ** n) / math.factorial(n)
                    for n in range(agents)
                ])
                erlangC = (traffic_power / agents_fact) * (agents / (agents - traffic_intensity))
                P_wait = erlangC / (sum_terms + erlangC)
                return P_wait

            def erlang_a(arrival_rate, service_rate, agents, patience):
                a = arrival_rate / service_rate
                rho = a / agents

                exp_neg_p = math.exp(-patience * (agents * service_rate - arrival_rate) / agents)
                if rho >= 1 or agents == 0:
                    return 100.0
                num = (a ** agents / math.factorial(agents)) * (1 - exp_neg_p)
                denom = sum([(a ** n) / math.factorial(n) for n in range(agents)]) + num
                p_abandon = num / denom if denom > 0 else 1.0
                return p_abandon * 100

            output_rows = []
            shrinkage_mult = 1 / ((1 - in_office_shrinkage / 100) * (1 - out_office_shrinkage / 100))
            for i, row in df.iterrows():
                call_volume = row[selected_day]
                interval = row['Interval']
                aht = asa_target
                arrival_rate = call_volume / 1800
                service_rate = 1 / aht

                traffic_intensity = arrival_rate * aht
                baseline_agents = max(1, math.ceil(traffic_intensity + 1))
                agent_needed = max(1, math.ceil(baseline_agents * shrinkage_mult))

                prob_wait, asa, service_level, abandon_rate, line_adherence = None, None, None, None, None

                if agent_needed > traffic_intensity:
                    prob_wait = erlang_c(traffic_intensity, agent_needed)
                    if prob_wait is not None:
                        try:
                            asa = (prob_wait * aht) / (agent_needed - traffic_intensity)
                        except ZeroDivisionError:
                            asa = None
                        service_level = (1 - prob_wait * math.exp(-(agent_needed - traffic_intensity) * (asa_target / aht))) * 100 if prob_wait is not None else None
                    # Abandon rate (Erlang A)
                    if selected_kpi == "Abandon Rate":
                        try:
                            abandon_rate = erlang_a(arrival_rate, service_rate, agent_needed, patience)
                        except Exception:
                            abandon_rate = None
                    # Line adherence (simulate as 100% if agent_needed met)
                    if selected_kpi == "Line Adherence":
                        # 100% since agent_needed always fully covered in this simplified model
                        line_adherence = 100 if agent_needed >= baseline_agents else round(100 * agent_needed / baseline_agents,2)

                if selected_kpi == "Service Level (SLA)":
                    value = None if service_level is None else round(service_level, 2)
                    met = None if value is None else ("Yes" if value >= target_kpi else "No")
                    kpi_label = "Service Level (%)"
                elif selected_kpi == "Average Speed of Answer (ASA)":
                    value = None if asa is None else round(asa, 2)
                    met = None if value is None else ("Yes" if value <= target_kpi else "No")
                    kpi_label = "ASA (seconds)"
                elif selected_kpi == "Abandon Rate":
                    value = None if abandon_rate is None else round(abandon_rate, 2)
                    met = None if value is None else ("Yes" if value <= target_kpi else "No")
                    kpi_label = "Abandon Rate (%)"
                elif selected_kpi == "Line Adherence":
                    value = None if line_adherence is None else round(line_adherence, 2)
                    met = None if value is None else ("Yes" if value >= target_kpi else "No")
                    kpi_label = "Line Adherence (%)"
                else:
                    value = None
                    met = None
                    kpi_label = selected_kpi

                output_rows.append({
                    "Interval": interval,
                    "Call Volume": call_volume,
                    "Agents Needed": agent_needed,
                    kpi_label: value,
                    "Target Met": met
                })

            output_df = pd.DataFrame(output_rows)
            st.subheader(f"Simulation Results for {selected_day}")
            st.dataframe(output_df)

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
            st.info("Coverage mode simulation logic coming next...")  # Placeholder!

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
    else:
        st.info("Paste your interval-level hours required (with headers) above to proceed.")
