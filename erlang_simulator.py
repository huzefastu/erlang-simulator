import streamlit as st
import pandas as pd
import math
import io

st.title("Contact Center Erlang Simulation")

sim_mode = st.radio(
    "Choose simulation mode:",
    ["Volume-based Requirement (Erlang)", "Hours-based Requirement (coverage)"]
)
st.write(f"**Simulation mode selected:** {sim_mode}")

# SIDEBAR CONTROLS
st.sidebar.header("KPI Setup")
kpi_options = ["Service Level (SLA)", "Abandon Rate", "Line Adherence", "Average Speed of Answer (ASA)"]
selected_kpi = st.sidebar.selectbox("KPI for Simulation", kpi_options)
target_kpi = st.sidebar.number_input(
    "Target " + selected_kpi + (" (%)" if "Rate" in selected_kpi or "Level" in selected_kpi else " (seconds)"),
    value=80 if selected_kpi == "Service Level (SLA)" else 10 if selected_kpi == "Abandon Rate" else 100 if selected_kpi == "Line Adherence" else 20,
    min_value=0, max_value=1000
)
asa_target = st.sidebar.number_input("ASA Target (seconds, always active)", value=20, min_value=1, max_value=1000)
target_scope = st.sidebar.selectbox("Should KPI be met per:", ["Interval", "Day", "Week"])
patience = st.sidebar.number_input("Average Caller Patience (seconds)", value=30, min_value=1, max_value=600,
                                   disabled=False if selected_kpi == "Abandon Rate" else True)
st.sidebar.header("Shrinkage Setup")
in_office_shrinkage = st.sidebar.number_input("In-office Shrinkage (%)", value=20, min_value=0, max_value=100)
out_office_shrinkage = st.sidebar.number_input("Out-of-office Shrinkage (%)", value=10, min_value=0, max_value=100)
st.sidebar.header("Shift & Agent Rules")
num_shifts = st.sidebar.number_input("Number of Different Shifts", value=3, min_value=1, max_value=10)
working_days_per_week = st.sidebar.number_input("Agent Working Days per Week", min_value=1, max_value=7, value=5)
min_shift_length = st.sidebar.number_input("Minimum Shift Length (hours)", min_value=1, max_value=12, value=4)
max_shift_length = st.sidebar.number_input("Maximum Shift Length (hours)", min_value=1, max_value=12, value=8)
total_agents = st.sidebar.number_input("Total FTE For Day", value=30, min_value=1, max_value=1000)

operating_hours = 24
interval_length_min = 30
weekdays_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

if sim_mode == "Volume-based Requirement (Erlang)":
    st.header("Paste Call Volume Table")
    st.markdown("*Header: Interval, Sunday, Monday, ..., Saturday*")
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
            valid_days = [d for d in weekdays_order if d in days]
            if not valid_days:
                st.error(f"No valid days found. Expected columns: {weekdays_order}. Found: {days}")
                st.stop()
            selected_day = st.selectbox("Select Day to Simulate", valid_days)
            if selected_day not in weekdays_order:
                st.error(f"Selected day '{selected_day}' not found in standard weekday list. Check your data headers.")
                st.stop()
            selected_day_idx = weekdays_order.index(selected_day)

            # Week-off Assignment
            days_in_week = 7
            week_offs_per_agent = days_in_week - working_days_per_week
            if week_offs_per_agent < 0:
                st.error("Working days/week cannot exceed 7.")
                st.stop()
            agent_week_off_distribution = [[] for _ in range(days_in_week)]
            agent_indices = list(range(total_agents))
            for idx, agent in enumerate(agent_indices):
                week_off_days = []
                for w in range(week_offs_per_agent):
                    week_off_day = (idx + w) % days_in_week
                    week_off_days.append(week_off_day)
                    agent_week_off_distribution[week_off_day].append(agent)

            agents_today = total_agents - len(agent_week_off_distribution[selected_day_idx])
            st.info(f"{agents_today} agents available on {selected_day} out of {total_agents} FTE.")

            # Auto Shift Generation
            num_intervals = int(operating_hours * 60 / interval_length_min)
            shift_length = max(min_shift_length, min(max_shift_length, int((operating_hours / num_shifts))))
            intervals_per_shift = int((shift_length * 60) / interval_length_min)
            shift_starts = [int(i * num_intervals // num_shifts) for i in range(num_shifts)]
            intervals = df['Interval'].tolist()
            agents_per_shift = [int(agents_today // num_shifts)] * num_shifts
            for i in range(agents_today % num_shifts):
                agents_per_shift[i] += 1

            # ---- OUTPUT (1): Agent Roster ----
            roster_output = []
            agent_id = 1
            for shift_idx, (shift_start, shift_agents) in enumerate(zip(shift_starts, agents_per_shift)):
                s_start = intervals[shift_start % num_intervals]
                s_end_idx = (shift_start + intervals_per_shift - 1) % num_intervals
                s_end = intervals[s_end_idx]
                # Find which agents are assigned to this shift
                for a in range(shift_agents):
                    agent_index = agent_id - 1
                    # Find week-offs for this agent
                    week_off_indices = [dow for dow, agents_lst in enumerate(agent_week_off_distribution) if agent_index in agents_lst]
                    week_off_labels = [weekdays_order[dow] for dow in week_off_indices][:2]
                    # Pad with '-' if <2 week-offs (for 6 or 7-day patterns)
                    while len(week_off_labels) < 2:
                        week_off_labels.append('-')
                    roster_output.append({
                        "Agent No.": agent_id,
                        "Shift Start Interval": s_start,
                        "Shift End Interval": s_end,
                        "Week Off 1": week_off_labels[0],
                        "Week Off 2": week_off_labels[1]
                    })
                    agent_id += 1
            st.subheader("Auto-Generated Agent Roster")
            st.dataframe(pd.DataFrame(roster_output))

            # Shift Coverage
            coverage = [0 for _ in range(num_intervals)]
            agent_pointer = 0
            agent_shifts = []
            for shift_idx, shift_start in enumerate(shift_starts):
                for a in range(agents_per_shift[shift_idx]):
                    shift_agent_intervals = []
                    for k in range(intervals_per_shift):
                        idx = (shift_start + k) % num_intervals
                        coverage[idx] += 1
                        shift_agent_intervals.append(idx)
                    agent_shifts.append(shift_agent_intervals)
                    agent_pointer += 1

            # KPI Simulation
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

            shrinkage_mult = 1 / ((1 - in_office_shrinkage / 100) * (1 - out_office_shrinkage / 100))
            interval_grid_rows = []
            for i, row in df.iterrows():
                call_volume = row[selected_day]
                interval = row['Interval']
                aht = asa_target
                arrival_rate = call_volume / 1800
                service_rate = 1 / aht

                agents_needed = max(1, math.ceil((arrival_rate * aht + 1) * shrinkage_mult))
                agents_covered = coverage[i]
                over_under = agents_covered - agents_needed
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
                interval_grid_rows.append({
                    "Interval": interval,
                    "Call Volume": call_volume,
                    "Agents Needed": agents_needed,
                    "Agents Scheduled": agents_covered,
                    kpi_label: value,
                    "Over/Under": over_under,
                    "Target Met": met,
                    "In-Office Shrinkage %": in_office_shrinkage
                })
            interval_grid_df = pd.DataFrame(interval_grid_rows)
            st.subheader("Interval Simulation Grid")
            st.dataframe(interval_grid_df)

            # ---- OUTPUT (3): Day-Level Totals ----
            st.subheader("Day-Level Totals")
            totals = {
                "Day Total Volume": interval_grid_df["Call Volume"].sum(),
                "Day Total Agents Needed": interval_grid_df["Agents Needed"].sum(),
                "Day Total Agents Scheduled": interval_grid_df["Agents Scheduled"].sum(),
                "Avg Agents Scheduled/Interval": round(interval_grid_df["Agents Scheduled"].mean(), 2),
                "Day KPI Avg": round(interval_grid_df[kpi_label].mean(), 2),
                "Intervals Meeting Target": int(interval_grid_df["Target Met"].eq("Yes").sum()),
                "Intervals Failing Target": int(interval_grid_df["Target Met"].eq("No").sum()),
                "Avg Over/Under": round(interval_grid_df["Over/Under"].mean(), 2),
                "In-Office Shrinkage %": in_office_shrinkage
            }
            st.write(pd.DataFrame(totals.items(), columns=["Metric", "Value"]))

            # Optional: Week-off distribution
            week_off_summary = {weekdays_order[d]: len(v) for d, v in enumerate(agent_week_off_distribution)}
            st.subheader("Week-off Distribution")
            st.write(pd.DataFrame(list(week_off_summary.items()), columns=['Day', 'Agents On Week-Off']))

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
