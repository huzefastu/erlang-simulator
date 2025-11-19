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
    f"SLA Target (%)", value=80, min_value=1, max_value=100
)
aht = st.sidebar.number_input("Average Handling Time (AHT, seconds)", min_value=1, max_value=3600, value=150, step=1)
asa_target = st.sidebar.number_input("SLA Window (seconds)", value=20, min_value=1, max_value=600)
# Shrinkage
st.sidebar.header("Shrinkage Setup")
in_office_shrinkage = st.sidebar.number_input("In-office Shrinkage (%)", value=20, min_value=0, max_value=100)
out_office_shrinkage = st.sidebar.number_input("Out-of-office Shrinkage (%)", value=10, min_value=0, max_value=100)
# Shift/Roster
st.sidebar.header("Shift & Agent Rules")
num_shifts = st.sidebar.number_input("Number of Shifts", value=3, min_value=1, max_value=10)
working_days_per_week = st.sidebar.number_input("Agent Working Days/Week", min_value=1, max_value=7, value=5)
min_shift_length = st.sidebar.number_input("Min Shift Length (hr)", min_value=1, max_value=12, value=4)
max_shift_length = st.sidebar.number_input("Max Shift Length (hr)", min_value=1, max_value=12, value=8)
total_agents = st.sidebar.number_input("Total FTE For Day", value=30, min_value=1, max_value=1000)

operating_hours = 24
interval_length_min = 30
weekdays_order = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
days_in_week = 7

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

def agents_needed_erlang_c(volume, aht, sla_seconds, sla_target, max_agents=100):
    calls_per_sec = float(volume) / 1800
    traffic_intensity = calls_per_sec * aht
    for agents in range(max(1, math.ceil(traffic_intensity)), max_agents+1):
        prob_wait = erlang_c(traffic_intensity, agents)
        if prob_wait is not None and agents > traffic_intensity:
            sla = (1 - prob_wait * math.exp(-(agents - traffic_intensity) * (sla_seconds / aht))) * 100
            if sla >= sla_target:
                return agents
    return max_agents

if sim_mode == "Volume-based Requirement (Erlang)":
    st.header("Paste Call Volume Table")
    st.markdown("*Paste intervals with volumes, no header. Columns must be: Interval, Sunday, Monday, ..., Saturday*")
    pasted_data = st.text_area("Paste volume table below (no header!):", height=400)
    column_headers = ["Interval"] + weekdays_order

    if pasted_data.strip():
        try:
            # Read data, assign headers
            df = pd.read_csv(io.StringIO(pasted_data), sep=None, engine="python", header=None)
            if df.shape[1] != len(column_headers):
                st.error(f"Expected {len(column_headers)} columns (Interval + 7 days). Found {df.shape[1]}.")
                st.stop()
            df.columns = column_headers
            intervals = df["Interval"].tolist()
            all_days = weekdays_order

            # Week-off assignment
            week_offs_per_agent = days_in_week - working_days_per_week
            agent_week_off_distribution = [[] for _ in range(days_in_week)]
            agent_indices = list(range(total_agents))
            for idx, agent in enumerate(agent_indices):
                for w in range(week_offs_per_agent):
                    week_off_day = (idx + w) % days_in_week
                    agent_week_off_distribution[week_off_day].append(agent)

            # Shift allocation
            agent_roster = []
            agent_id = 1
            num_intervals = len(intervals)
            shift_length = max(min_shift_length, min(max_shift_length, int(operating_hours / num_shifts)))
            intervals_per_shift = int((shift_length * 60) // interval_length_min)
            shift_starts = [int(i * num_intervals // num_shifts) for i in range(num_shifts)]
            agents_per_shift = [int(total_agents // num_shifts)] * num_shifts
            for i in range(total_agents % num_shifts):
                agents_per_shift[i] += 1

            # AGENT ROSTER GRID
            for shift_idx, (start, count) in enumerate(zip(shift_starts, agents_per_shift)):
                s_start = intervals[start % num_intervals]
                s_end = intervals[(start + intervals_per_shift - 1) % num_intervals]
                for a in range(count):
                    idx = agent_id - 1
                    week_off_indices = [dow for dow, lst in enumerate(agent_week_off_distribution) if idx in lst]
                    week_off_labels = [weekdays_order[dow] for dow in week_off_indices][:2]
                    while len(week_off_labels) < 2:
                        week_off_labels.append("-")
                    agent_roster.append([agent_id, s_start, s_end, week_off_labels[0], week_off_labels[1]])
                    agent_id += 1
            st.subheader("Agent Roster")
            st.dataframe(pd.DataFrame(agent_roster, columns=["Agent ID", "Shift Start", "Shift End", "Week Off 1", "Week Off 2"]))

            # Coverage for all days/intervals
            coverage_matrix = [[0 for _ in range(days_in_week)] for _ in range(num_intervals)]
            pointer = 0
            for shift_idx, shift_start in enumerate(shift_starts):
                for a in range(agents_per_shift[shift_idx]):
                    agent_num = pointer
                    for day_idx in range(days_in_week):
                        if agent_num not in agent_week_off_distribution[day_idx]:
                            covered_idxs = [(shift_start + k) % num_intervals for k in range(intervals_per_shift)]
                            for idx in covered_idxs:
                                coverage_matrix[idx][day_idx] += 1
                    pointer += 1

            # SHRINKAGE FACTOR (if needed elsewhere)
            shrinkage_mult = 1 / ((1 - in_office_shrinkage / 100) * (1 - out_office_shrinkage / 100))

            # Grids
            results_needed, results_sched, results_open = [], [], []
            for idx, interval in enumerate(intervals):
                row_needed = [interval]
                row_sched = [interval]
                row_open = [interval]
                for day_idx, day in enumerate(weekdays_order):
                    call_volume = df.loc[idx, day]
                    agents_scheduled = coverage_matrix[idx][day_idx]
                    agents_needed = agents_needed_erlang_c(call_volume, aht, asa_target, target_kpi)
                    agents_open = round(agents_scheduled * (1 - in_office_shrinkage / 100), 2)
                    row_needed.append(agents_needed)
                    row_sched.append(agents_scheduled)
                    row_open.append(agents_open)
                results_needed.append(row_needed)
                results_sched.append(row_sched)
                results_open.append(row_open)

            # Day averages for bottom row
            row_avg_needed = ["Day Average"]
            row_avg_sched = ["Day Average"]
            row_avg_open = ["Day Average"]
            for day_idx in range(len(weekdays_order)):
                needed_vals = [results_needed[i][day_idx + 1] for i in range(len(results_needed))]
                sched_vals = [results_sched[i][day_idx + 1] for i in range(len(results_sched))]
                open_vals = [results_open[i][day_idx + 1] for i in range(len(results_open))]
                row_avg_needed.append(round(sum(needed_vals) / len(needed_vals), 2))
                row_avg_sched.append(round(sum(sched_vals) / len(sched_vals), 2))
                row_avg_open.append(round(sum(open_vals) / len(open_vals), 2))
            results_needed.append(row_avg_needed)
            results_sched.append(row_avg_sched)
            results_open.append(row_avg_open)

            st.subheader("Grid 1: Agents Needed (Erlang C - SLA Target)")
            st.dataframe(pd.DataFrame(results_needed, columns=["Interval"] + weekdays_order))
            st.subheader("Grid 2: Agents Scheduled (Roster/Shift)")
            st.dataframe(pd.DataFrame(results_sched, columns=["Interval"] + weekdays_order))
            st.subheader("Grid 3: Agents Open (After In-Office Shrinkage)")
            st.dataframe(pd.DataFrame(results_open, columns=["Interval"] + weekdays_order))
        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")

results_kpi, results_over = [], []

for idx, interval in enumerate(intervals):
    row_kpi = [interval]
    row_over = [interval]
    for day_idx, day in enumerate(weekdays_order):
        call_volume = df.loc[idx, day]
        agents_scheduled = coverage_matrix[idx][day_idx]
        agents_needed = results_needed[idx][day_idx + 1]  # from previous grid!
        over_under = agents_scheduled - agents_needed

        calls_per_sec = float(call_volume) / 1800
        traffic_intensity = calls_per_sec * aht

        # KPI calculations
        prob_wait = erlang_c(traffic_intensity, agents_scheduled)
        service_level = asa = abandon_rate = line_adherence = None
        if prob_wait is not None and agents_scheduled > traffic_intensity:
            asa = (prob_wait * aht) / (agents_scheduled - traffic_intensity)
            service_level = (1 - prob_wait * math.exp(-(agents_scheduled - traffic_intensity) * (asa_target / aht))) * 100
        if selected_kpi == "Abandon Rate":
            def erlang_a(arrival_rate, service_rate, agents, patience):
                a = arrival_rate / service_rate
                rho = a / agents
                exp_neg_p = math.exp(-patience * (agents * service_rate - arrival_rate) / agents)
                if rho >= 1 or agents == 0:
                    return 100.0
                num = (a ** agents / math.factorial(agents)) * (1 - exp_neg_p)
                denom = sum([(a ** n) / math.factorial(n) for n in range(agents)]) + num
                p_abandon = num / denom if denom > 0 else 1.0
