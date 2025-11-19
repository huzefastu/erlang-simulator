import streamlit as st
import pandas as pd
import math
import io

st.title("Contact Center Erlang Simulation")

# Input controls (same as before) ...
sim_mode = st.radio(
    "Choose simulation mode:",
    ["Volume-based Requirement (Erlang)", "Hours-based Requirement (coverage)"]
)
st.write(f"**Simulation mode selected:** {sim_mode}")

st.sidebar.header("KPI Setup")
kpi_options = ["Service Level (SLA)", "Abandon Rate", "Line Adherence", "Average Speed of Answer (ASA)"]
selected_kpi = st.sidebar.selectbox("KPI for Simulation", kpi_options)
target_kpi = st.sidebar.number_input(
    "Target " + selected_kpi + (" (%)" if "Rate" in selected_kpi or "Level" in selected_kpi else " (seconds)"),
    value=80 if selected_kpi == "Service Level (SLA)" else 10 if selected_kpi == "Abandon Rate" else 100 if selected_kpi == "Line Adherence" else 20,
    min_value=0, max_value=1000
)
asa_target = st.sidebar.number_input("ASA Target (seconds, always active)", value=20, min_value=1, max_value=1000)
patience = st.sidebar.number_input("Avg Caller Patience (s)", 30, 1, 600,
    disabled=False if selected_kpi == "Abandon Rate" else True)
st.sidebar.header("Shrinkage Setup")
in_office_shrinkage = st.sidebar.number_input("In-office Shrinkage (%)", value=20, min_value=0, max_value=100)
out_office_shrinkage = st.sidebar.number_input("Out-of-office Shrinkage (%)", value=10, min_value=0, max_value=100)
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

if sim_mode == "Volume-based Requirement (Erlang)":
    st.header("Paste Call Volume Table")
    st.markdown("*Paste with header: Interval, Sunday, Monday, ..., Saturday*")
    pasted_data = st.text_area("Paste your table data below (include header):", height=300)
    if pasted_data.strip():
        try:
            df = pd.read_csv(io.StringIO(pasted_data), sep=None, engine="python")
            if "Interval" not in df.columns:
                st.error("Header row must include 'Interval'!")
                st.stop()
            intervals = df["Interval"].tolist()
            all_days = [d for d in df.columns if d != "Interval"]

            # 1. AUTOGENERATE WEEK-OFFS
            week_offs_per_agent = days_in_week - working_days_per_week
            agent_week_off_distribution = [[] for _ in range(days_in_week)]
            agent_indices = list(range(total_agents))
            for idx, agent in enumerate(agent_indices):
                for w in range(week_offs_per_agent):
                    week_off_day = (idx + w) % days_in_week
                    agent_week_off_distribution[week_off_day].append(agent)
            # AGENT ROSTER TABLE (Grid 1)
            agent_roster = []
            agent_day_shifts = []
            num_intervals = len(intervals)
            shift_length = max(min_shift_length, min(max_shift_length, int(operating_hours / num_shifts)))
            intervals_per_shift = int((shift_length * 60) // interval_length_min)
            shift_starts = [int(i * num_intervals // num_shifts) for i in range(num_shifts)]
            # Assign as evenly as possible
            agents_per_shift = [int(total_agents // num_shifts)] * num_shifts
            for i in range(total_agents % num_shifts):
                agents_per_shift[i] += 1
            agent_id = 1
            for shift_idx, (start, count) in enumerate(zip(shift_starts, agents_per_shift)):
                s_start = intervals[start % num_intervals]
                s_end = intervals[(start + intervals_per_shift - 1) % num_intervals]
                for a in range(count):
                    idx = agent_id - 1
                    # Agent week-offs
                    week_off_indices = [dow for dow, lst in enumerate(agent_week_off_distribution) if idx in lst]
                    week_off_labels = [weekdays_order[dow] for dow in week_off_indices][:2]
                    while len(week_off_labels) < 2:
                        week_off_labels.append("-")
                    agent_roster.append([agent_id, s_start, s_end, week_off_labels[0], week_off_labels[1]])
                    agent_id += 1
            st.subheader("Grid 1: Agent Roster")
            st.dataframe(pd.DataFrame(agent_roster, columns=["Agent ID", "Shift Start", "Shift End", "Week Off 1", "Week Off 2"]))

            # 2. COVERAGE LOGIC FOR ALL DAYS AND INTERVALS
            shrinkage_mult = 1 / ((1 - in_office_shrinkage / 100) * (1 - out_office_shrinkage / 100))
            day_grids = {k: [] for k in ["kpi", "over", "shrink"]}
            results_kpi = []
            results_over = []
            results_shrink = []
            for idx, interval in enumerate(intervals):
                row_kpi = [interval]
                row_over = [interval]
                row_shrink = [interval]
                for day_idx, day in enumerate(weekdays_order):
                    # ------------- Calculate scheduled agents for this interval and day -------------
                    # Agents present = only those not off duty for this day, who are scheduled for interval
                    agents_off_today = set(agent_week_off_distribution[day_idx])
                    scheduled_today = []
                    pointer = 0
                    for shift_i, (start, count) in enumerate(zip(shift_starts, agents_per_shift)):
                        for a in range(count):
                            agent_num = pointer
                            if agent_num not in agents_off_today:
                                # Interval coverage for this shift
                                covered_idxs = [(start + k) % num_intervals for k in range(intervals_per_shift)]
                                if idx in covered_idxs:
                                    scheduled_today.append(agent_num)
                            pointer += 1
                    call_volume = df.loc[idx, day] if day in df.columns else 0
                    aht = asa_target
                    arrival_rate = float(call_volume) / 1800
                    agents_covered = len(scheduled_today)
                    traffic_intensity = arrival_rate * aht
                    agents_needed = max(1, math.ceil((arrival_rate * aht + 1) * shrinkage_mult))
                    over_under = agents_covered - agents_needed
                    # ---- KPI Calculation ----
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

                    if agents_covered > 0:
                        prob_wait = erlang_c(traffic_intensity, agents_covered)
                        service_level = None
                        asa = None
                        abandon_rate = None
                        line_adherence = None
                        if prob_wait is not None and agents_covered > traffic_intensity:
                            asa = (prob_wait * aht) / (agents_covered - traffic_intensity)
                            service_level = (1 - prob_wait * math.exp(-(agents_covered - traffic_intensity) * (asa_target / aht))) * 100
                        if selected_kpi == "Abandon Rate":
                            abandon_rate = erlang_a(arrival_rate, 1/aht, agents_covered, patience)
                        if selected_kpi == "Line Adherence":
                            line_adherence = round(100 * agents_covered / agents_needed, 2) if agents_needed > 0 else 100
                    else:
                        service_level = asa = abandon_rate = line_adherence = None
                    if selected_kpi == "Service Level (SLA)":
                        value = None if service_level is None else round(service_level, 2)
                    elif selected_kpi == "Average Speed of Answer (ASA)":
                        value = None if asa is None else round(asa, 2)
                    elif selected_kpi == "Abandon Rate":
                        value = None if abandon_rate is None else round(abandon_rate, 2)
                    elif selected_kpi == "Line Adherence":
                        value = None if line_adherence is None else round(line_adherence, 2)
                    else:
                        value = None
                    row_kpi.append(value)
                    row_over.append(over_under)
                    row_shrink.append(in_office_shrinkage)
                results_kpi.append(row_kpi)
                results_over.append(row_over)
                results_shrink.append(row_shrink)
            # GRID 2: KPI per interval & day
            st.subheader("Grid 2: KPI Per Interval & Day")
            st.dataframe(pd.DataFrame(results_kpi, columns=["Interval"] + weekdays_order))
            # GRID 3: Over/Under per interval & day
            st.subheader("Grid 3: Overs/Unders")
            st.dataframe(pd.DataFrame(results_over, columns=["Interval"] + weekdays_order))
            # GRID 4: Shrinkage per interval & day
            st.subheader("Grid 4: In-Office Shrinkage (%)")
            st.dataframe(pd.DataFrame(results_shrink, columns=["Interval"] + weekdays_order))

        except Exception as e:
            st.error(f"Could not parse table data. Error: {e}")
