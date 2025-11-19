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
kpi_options = ["Service Level (SLA)", "Abandon Rate", "Line Adherence", "Average Speed of Answer (ASA)"]
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
total_agents = st.sidebar.number_input("Total FTE For Day", value=30, min_value=1, max_value=1000)

operating_hours = 24
interval_length_min = 30

weekdays_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

st.markdown(f"""**Sidebar KPI, Shrinkage, Shift/Agent Rules Setup**:  
- **Shifts:** {num_shifts} × {min_shift_length}-{max_shift_length} hr  
- **Total agents (FTE):** {total_agents}  
- **Working Days Per Agent:** {working_days_per_week}
""")

if sim_mode == "Volume-based Requirement (Erlang)":
    st.header("Paste Call Volume Table")
    st.markdown("*Copy 30-min interval data from Excel, header must be: Interval, Sunday, Monday, ..., Saturday*")
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
            # Days in pasted table may be different order; force our standard
            valid_days = [d for d in weekdays_order if d in days]
            selected_day = st.selectbox("Select Day to Simulate", valid_days)

            # Week-off assignment logic
            days_in_week = 7
            week_offs_per_agent = days_in_week - working_days_per_week
            agent_week_off_distribution = [[] for _ in range(days_in_week)]

            # Distribute total_agents as evenly as possible having weekoffs on each day
            agent_indices = list(range(total_agents))
            # Assign week-offs in round-robin order to balance agent coverage
            for idx, agent in enumerate(agent_indices):
                week_off_days = []
                for w in range(week_offs_per_agent):
                    week_off_day = (idx + w) % days_in_week
                    week_off_days.append(week_off_day)
                    agent_week_off_distribution[week_off_day].append(agent)
            # For the selected day, available agents = total_agents - week_off_count on that day
            selected_day_idx = weekdays_order.index(selected_day)
            agents_today = total_agents - len(agent_week_off_distribution[selected_day_idx])

            st.info(f"{agents_today} agents are available for shifts on {selected_day}, based on {total_agents} FTE and {working_days_per_week} working days/week.")

            # ---- Shift Auto-generation ----
            num_intervals = int(operating_hours * 60 / interval_length_min)
            shift_length = max(min_shift_length, min(max_shift_length, int((operating_hours / num_shifts))))
            intervals_per_shift = int((shift_length * 60) / interval_length_min)
            shift_starts = [int(i * num_intervals / num_shifts) for i in range(num_shifts)]
            intervals = df['Interval'].tolist()

            agents_per_shift = [int(agents_today // num_shifts)] * num_shifts
            for i in range(agents_today % num_shifts):
                agents_per_shift[i] += 1

            shifts = []
            for idx, start in enumerate(shift_starts):
                s_start = intervals[start % num_intervals]
                s_end_idx = (start + intervals_per_shift - 1) % num_intervals
                s_end = intervals[s_end_idx]
                shifts.append({
                    "Shift #": idx + 1,
                    "Start Interval": s_start,
                    "End Interval": s_end,
                    "Intervals Covered": intervals_per_shift,
                    "Agents": agents_per_shift[idx]
                })
            st.subheader("Auto-Generated Shifts (Demo):")
            st.dataframe(pd.DataFrame(shifts))

            # Map agent coverage per interval
            coverage = [0 for _ in range(num_intervals)]
            for i, shift_start in enumerate(shift_starts):
                for k in range(intervals_per_shift):
                    idx = (shift_start + k) % num_intervals
                    coverage[idx] += agents_per_shift[i]

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

                agents_needed = max(1, math.ceil((arrival_rate * aht + 1) * shrinkage_mult))
                agents_covered = coverage[i]

                value, met, kpi_label = None, None, selected_kpi
                prob_wait, asa, service_level, abandon_rate, line_adherence = None, None, None, None, None

                if agents_covered > 0:
                    traffic_intensity = arrival_rate * aht
                    prob_wait = erlang_c(traffic_intensity, agents_covered)
                    if prob_wait is not None and agents_covered > traffic_intensity:
                        asa = (prob_wait * aht) / (agents_covered - traffic_intensity)
                        service_level = (1 - prob_wait * math.exp(-(agents_covered - traffic_intensity) * (asa_target / aht))) * 100
                    if selected_kpi == "Abandon Rate":
                        abandon_rate = erlang_a(arrival_rate, service_rate, agents_covered, patience)
                    if selected_kpi == "Line Adherence":
                        line_adherence = round(100 * agents_covered / agents_needed, 2) if agents_needed > 0 else 100

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
                    "Agents Needed": agents_needed,
                    "Agents Scheduled": agents_covered,
                    kpi_label: value,
                    "Target Met": met
                })

            output_df = pd.DataFrame(output_rows)
            st.subheader(f"Simulation Results for {selected_day}")
            st.dataframe(output_df)

            # Show week-off distribution
            week_off_summary = {weekdays_order[d]: len(v) for d, v in enumerate(agent_week_off_distribution)}
            st.subheader("Week-off Distribution")
            st.write(pd.DataFrame(list(week_off_summary.items()), columns=['Day', 'Agents On Week-Off']))

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
