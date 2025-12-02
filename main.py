# main.py
#
# Wizard: Pages 1–9
# Run with: streamlit run main.py

import streamlit as st
import pandas as pd

from erlang_engine import (
    required_agents_and_hours_sla,
    required_agents_and_hours_asa,
)


# --- helpers to manage wizard page number --- #

def init_wizard_state():
    if "wizard_page" not in st.session_state:
        st.session_state["wizard_page"] = 1

    # Global config defaults
    if "config" not in st.session_state:
        st.session_state["config"] = {
            "interval_minutes": 30,
            "requirement_type": "volume",  # "volume" or "hours"
            "kpi_type": "sl",              # "sl", "asa", "line_adherence"
            "kpi_aggregation_level": "interval",  # "interval", "day", or "week"
            "kpi_targets": {
                "sla": 0.8,                # 80%
                "service_time_sec": 20,
                "abandon_pct": 0.02,       # 2%
                "abandon_time_sec": 30,
                "asa_sec": 20,
                "interval_target_pct": 0.95,
                "day_target_pct": 0.95,
            },
            "shrinkage": {
                "out_office_pct": 0.15,   # 15% external shrinkage
                "in_office_pct": 0.10,    # 10% internal shrinkage (breaks etc.)
            },
        }

    if "data" not in st.session_state:
        st.session_state["data"] = {
            "volume": None,
            "aht": None,
            "required_hours": None,
            "required_agents": None,
            "roster_counts_raw": None,
            "roster_after_ooo": None,
            "roster_after_all_shrinkage": None,
            "open_count": None,
            "over_under": None,
        }

    if "agent_types" not in st.session_state:
        st.session_state["agent_types"] = []

    if "agent_type_edit_index" not in st.session_state:
        st.session_state["agent_type_edit_index"] = None


def make_empty_week_grid(interval_minutes: int) -> "pd.DataFrame":
    """
    Create an empty week grid with:
    - Rows: time labels like '00:00', '00:15', ...
    - Columns: days Sun–Sat
    """
    intervals_per_day = int(24 * 60 / interval_minutes)
    labels = []
    for i in range(intervals_per_day):
        total_minutes = i * interval_minutes
        hour = total_minutes // 60
        minute = total_minutes % 60
        labels.append(f"{hour:02d}:{minute:02d}")
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    return pd.DataFrame(0.0, index=labels, columns=days)


def go_to_page(page_number: int):
    st.session_state["wizard_page"] = page_number


# --- Page 1: KPI and assumption inputs --- #

def page_1():
    st.title("Erlang Simulator Wizard")
    st.header("Page 1: KPI and Assumption Inputs")

    config = st.session_state["config"]

    st.subheader("Interval Size")
    interval_size = st.radio(
        "Choose interval length:",
        options=[15, 30, 60],
        index=[15, 30, 60].index(config["interval_minutes"]),
        horizontal=True,
    )

    st.subheader("Requirement Type")
    requirement_type = st.radio(
        "How do you want to give requirements?",
        options=["volume", "hours"],
        format_func=lambda x: "Volume-based (Erlang) " if x == "volume" else "Hours-based (manual)",
        index=0 if config["requirement_type"] == "volume" else 1,
    )

    st.subheader("KPI Type")
    kpi_options = ["sl", "asa"]
    kpi_labels = {
        "sl": "Service Level",
        "asa": "Average Speed of Answer (ASA)",
        "line_adherence": "Line Adherence (hours mode only)",
    }
    if requirement_type == "hours":
        kpi_options.append("line_adherence")

    current_kpi = config["kpi_type"]
    if current_kpi not in kpi_options:
        current_kpi = "sl"

    kpi_type = st.radio(
        "Which KPI do you want to design for?",
        options=kpi_options,
        format_func=lambda x: kpi_labels[x],
        index=kpi_options.index(current_kpi),
    )

    st.subheader("KPI Target Level")
    agg_level_labels = {
        "interval": "Interval Level (each time slot)",
        "day": "Day Level (average per day)",
        "week": "Week Level (overall week)",
    }
    current_level = config.get("kpi_aggregation_level", "interval")
    kpi_aggregation_level = st.radio(
        "At what level should the KPI target be met?",
        options=["interval", "day", "week"],
        format_func=lambda x: agg_level_labels[x],
        index=["interval", "day", "week"].index(current_level),
    )

    st.subheader("KPI Targets (Global for Week)")
    kpi_targets = config["kpi_targets"]

    if kpi_type == "sl":
        col1, col2 = st.columns(2)
        with col1:
            sla_pct = st.number_input(
                "Service Level Target (%)",
                min_value=0.0,
                max_value=100.0,
                value=kpi_targets["sla"] * 100,
                step=1.0,
            )
            service_time_sec = st.number_input(
                "Service Time Target (seconds)",
                min_value=1,
                max_value=600,
                value=kpi_targets["service_time_sec"],
                step=1,
            )
        with col2:
            abandon_pct = st.number_input(
                "Abandon Target (%)",
                min_value=0.0,
                max_value=100.0,
                value=kpi_targets["abandon_pct"] * 100,
                step=0.5,
            )
            abandon_time_sec = st.number_input(
                "Abandon Time (seconds)",
                min_value=1,
                max_value=600,
                value=kpi_targets["abandon_time_sec"],
                step=1,
            )

        kpi_targets["sla"] = sla_pct / 100.0
        kpi_targets["service_time_sec"] = int(service_time_sec)
        kpi_targets["abandon_pct"] = abandon_pct / 100.0
        kpi_targets["abandon_time_sec"] = int(abandon_time_sec)

    elif kpi_type == "asa":
        asa_sec = st.number_input(
            "ASA Target (seconds)",
            min_value=1,
            max_value=600,
            value=kpi_targets["asa_sec"],
            step=1,
        )
        kpi_targets["asa_sec"] = int(asa_sec)

    elif kpi_type == "line_adherence":
        col1, col2 = st.columns(2)
        with col1:
            interval_target_pct = st.number_input(
                "Interval Adherence Target (%)",
                min_value=0.0,
                max_value=100.0,
                value=kpi_targets["interval_target_pct"] * 100,
                step=1.0,
            )
        with col2:
            day_target_pct = st.number_input(
                "Day Adherence Target (%)",
                min_value=0.0,
                max_value=100.0,
                value=kpi_targets["day_target_pct"] * 100,
                step=1.0,
            )
        kpi_targets["interval_target_pct"] = interval_target_pct / 100.0
        kpi_targets["day_target_pct"] = day_target_pct / 100.0

    st.subheader("Shrinkage Targets")
    col1, col2 = st.columns(2)
    with col1:
        out_office_pct = st.number_input(
            "Out-of-Office Shrinkage (%)",
            min_value=0.0,
            max_value=100.0,
            value=config["shrinkage"]["out_office_pct"] * 100,
            step=1.0,
        )
    with col2:
        in_office_pct = st.number_input(
            "In-Office Shrinkage (%)",
            min_value=0.0,
            max_value=100.0,
            value=config["shrinkage"]["in_office_pct"] * 100,
            step=1.0,
        )

    st.write("These are global shrinkage targets for the whole week.")

    config["interval_minutes"] = int(interval_size)
    config["requirement_type"] = requirement_type
    config["kpi_type"] = kpi_type
    config["kpi_aggregation_level"] = kpi_aggregation_level
    config["kpi_targets"] = kpi_targets
    config["shrinkage"]["out_office_pct"] = out_office_pct / 100.0
    config["shrinkage"]["in_office_pct"] = in_office_pct / 100.0
    st.session_state["config"] = config

    st.markdown("---")
    if st.button("Next ➜"):
        go_to_page(2)


# --- Page 2: Volume Forecast --- #

def page_2():
    st.title("Erlang Simulator Wizard")
    st.header("Page 2: Volume Forecast Inputs")
    config = st.session_state["config"]
    data = st.session_state["data"]

    interval_minutes = config["interval_minutes"]

    if data["volume"] is None:
        data["volume"] = make_empty_week_grid(interval_minutes)

    volume_df = data["volume"]

    st.write("Enter forecasted call volumes per interval for each day (Sun–Sat).")
    st.write("You can start simple: maybe fill just one day to test.")

    edited_df = st.data_editor(
        volume_df,
        num_rows="dynamic",
        use_container_width=True,
        key="volume_editor",
    )

    data["volume"] = edited_df
    st.session_state["data"] = data

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅ Back to Page 1"):
            go_to_page(1)
    with col2:
        if st.button("Next ➜ Page 3"):
            go_to_page(3)


# --- Page 3: AHT Forecast --- #

def page_3():
    st.title("Erlang Simulator Wizard")
    st.header("Page 3: AHT Forecast Inputs")
    config = st.session_state["config"]
    data = st.session_state["data"]

    interval_minutes = config["interval_minutes"]

    if data["aht"] is None:
        df = make_empty_week_grid(interval_minutes)
        df[:] = 180
        data["aht"] = df

    aht_df = data["aht"]

    st.write("Enter AHT (in seconds) per interval for each day.")
    st.write("You can keep it constant (e.g., 180) at first.")

    edited_df = st.data_editor(
        aht_df,
        num_rows="dynamic",
        use_container_width=True,
        key="aht_editor",
    )

    data["aht"] = edited_df
    st.session_state["data"] = data

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅ Back to Page 2"):
            go_to_page(2)
    with col3:
        if st.button("Next ➜ Page 4"):
            go_to_page(4)


# --- Page 4: Agent Shift Inputs and Constraints --- #

def page_4():
    st.title("Erlang Simulator Wizard")
    st.header("Page 4: Agent Shift Inputs and Constraints")

    agent_types = st.session_state.get("agent_types", [])
    edit_index = st.session_state.get("agent_type_edit_index", None)
    editing_type = None
    if edit_index is not None and 0 <= edit_index < len(agent_types):
        editing_type = agent_types[edit_index]

    st.write("Define one or more agent types and their shift rules.")
    st.write("We will use these later to build rosters and breaks.")

    with st.form("add_agent_type_form"):
        st.subheader("Add / Edit Agent Type")

        name = st.text_input(
            "Agent Type Name",
            value=editing_type["name"] if editing_type else "Default Type",
        )

        col1, col2 = st.columns(2)
        with col1:
            num_agents = st.number_input(
                "Number of Agents",
                min_value=0,
                max_value=10000,
                value=editing_type["num_agents"] if editing_type else 10,
                step=1,
            )
            shift_length_hours = st.number_input(
                "Shift Length (hours)",
                min_value=1.0,
                max_value=24.0,
                value=editing_type["shift_length_hours"] if editing_type else 8.0,
                step=0.5,
            )
        with col2:
            weekoffs_per_agent = st.number_input(
                "Number of Week-offs per Week",
                min_value=0,
                max_value=7,
                value=editing_type["weekoffs_per_agent"] if editing_type else 2,
                step=1,
            )
            min_rest_hours = st.number_input(
                "Minimum Rest Time Between Shifts (hours)",
                min_value=0.0,
                max_value=48.0,
                value=editing_type["min_rest_hours"] if editing_type else 12.0,
                step=1.0,
            )

        st.markdown("**Break Lengths (minutes)**")
        bcol1, bcol2, bcol3 = st.columns(3)
        existing_breaks = editing_type["breaks_min"] if editing_type else [15, 30, 15]
        with bcol1:
            break1 = st.number_input(
                "Break 1",
                min_value=0,
                max_value=120,
                value=existing_breaks[0],
                step=5,
            )
        with bcol2:
            break2 = st.number_input(
                "Lunch",
                min_value=0,
                max_value=120,
                value=existing_breaks[1],
                step=5,
            )
        with bcol3:
            break3 = st.number_input(
                "Break 2",
                min_value=0,
                max_value=120,
                value=existing_breaks[2],
                step=5,
            )

        consecutive_weekoffs = st.checkbox(
            "Consecutive Week-Offs Required?",
            value=editing_type["consecutive_weekoffs"] if editing_type else True,
        )

        max_working_days_between_weekoffs = st.number_input(
            "Max Working Days Between Week-offs",
            min_value=1,
            max_value=14,
            value=editing_type["max_days_between_weekoffs"] if editing_type else 6,
            step=1,
        )

        st.markdown("**Hours of Operation**")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            start_time = st.time_input(
                "Start Time",
                value=editing_type["start_time"] if editing_type else pd.to_datetime("09:00").time(),
            )
        with col_t2:
            end_time = st.time_input(
                "End Time",
                value=editing_type["end_time"] if editing_type else pd.to_datetime("18:00").time(),
            )

        st.markdown("**Working Days**")
        day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        working_days = []
        existing_days = editing_type["working_days"] if editing_type else None
        day_cols = st.columns(7)
        for i, day in enumerate(day_labels):
            with day_cols[i]:
                if existing_days is not None:
                    default_checked = day in existing_days
                else:
                    default_checked = day in ["Mon", "Tue", "Wed", "Thu", "Fri"]
                checked = st.checkbox(
                    day,
                    value=default_checked,
                    key=f"wd_{day}_{edit_index}",
                )
                if checked:
                    working_days.append(day)

        button_label = "💾 Update Agent Type" if editing_type else "➕ Add Agent Type"
        submit = st.form_submit_button(button_label)

    if submit:
        new_type = {
            "name": name.strip() or "Agent Type",
            "num_agents": int(num_agents),
            "shift_length_hours": float(shift_length_hours),
            "breaks_min": [int(break1), int(break2), int(break3)],
            "weekoffs_per_agent": int(weekoffs_per_agent),
            "consecutive_weekoffs": bool(consecutive_weekoffs),
            "max_days_between_weekoffs": int(max_working_days_between_weekoffs),
            "min_rest_hours": float(min_rest_hours),
            "start_time": start_time,
            "end_time": end_time,
            "working_days": working_days,
        }

        if editing_type is not None:
            agent_types[edit_index] = new_type
            st.session_state["agent_types"] = agent_types
            st.session_state["agent_type_edit_index"] = None
            st.success(f"Agent type '{new_type['name']}' updated.")
            st.rerun()
        else:
            agent_types.append(new_type)
            st.session_state["agent_types"] = agent_types
            st.success(f"Agent type '{new_type['name']}' added.")
            st.rerun()

    st.markdown("### Current Agent Types")

    if agent_types:
        delete_index = None
        edit_clicked_index = None

        for idx, atype in enumerate(agent_types):
            col_info, col_edit, col_delete = st.columns([4, 1, 1])
            with col_info:
                days_str = ", ".join(atype.get("working_days", []))
                st.write(
                    f"{idx + 1}. {atype['name']} - "
                    f"{atype['num_agents']} agents, "
                    f"{atype['shift_length_hours']}h shift, "
                    f"Week-offs: {atype['weekoffs_per_agent']}  \n"
                    f"Hours: {atype.get('start_time')}–{atype.get('end_time')}  \n"
                    f"Working Days: {days_str}"
                )
            with col_edit:
                if st.button("✏️ Edit", key=f"edit_agent_type_{idx}"):
                    edit_clicked_index = idx
            with col_delete:
                if st.button("🗑️ Delete", key=f"delete_agent_type_{idx}"):
                    delete_index = idx

        if edit_clicked_index is not None:
            st.session_state["agent_type_edit_index"] = edit_clicked_index
            st.rerun()

        if delete_index is not None:
            agent_types.pop(delete_index)
            st.session_state["agent_types"] = agent_types
            if st.session_state.get("agent_type_edit_index") == delete_index:
                st.session_state["agent_type_edit_index"] = None
            st.rerun()
    else:
        st.info("No agent types added yet. Use the form above to add one.")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅ Back to Page 3"):
            go_to_page(3)
    with col3:
        if st.button("Next ➜ Page 5 (Required Hours)"):
            go_to_page(5)


# --- Page 5: Required Hours and Agents --- #

def page_5():
    st.title("Erlang Simulator Wizard")
    st.header("Page 5: Required Hours and Agents")

    config = st.session_state["config"]
    data = st.session_state["data"]

    interval_minutes = config["interval_minutes"]
    interval_hours = interval_minutes / 60.0

    requirement_type = config["requirement_type"]
    kpi_type = config["kpi_type"]
    kpi_targets = config["kpi_targets"]

    volume_df = data.get("volume")
    aht_df = data.get("aht")

    if volume_df is None or aht_df is None:
        st.error("Please complete Page 2 (Volume) and Page 3 (AHT) first.")
        if st.button("⬅ Back to Page 2"):
            go_to_page(2)
        return

    st.write(f"Interval length: {interval_minutes} minutes.")

    if requirement_type == "volume":
        st.subheader("Requirement Type: Volume (calculated via Erlang)")

        if kpi_type == "sl":
            st.write("KPI: Service Level – calculating agents and hours from Volume + AHT.")
            target_sla = kpi_targets["sla"]
            target_answer_time = kpi_targets["service_time_sec"]

            req_agents, req_hours = required_agents_and_hours_sla(
                volume_df=volume_df,
                aht_df=aht_df,
                target_sla=target_sla,
                target_answer_time_seconds=target_answer_time,
                interval_minutes=interval_minutes,
            )

        elif kpi_type == "asa":
            st.write("KPI: ASA – calculating agents and hours from Volume + AHT.")
            target_asa = kpi_targets["asa_sec"]

            req_agents, req_hours = required_agents_and_hours_asa(
                volume_df=volume_df,
                aht_df=aht_df,
                target_asa_seconds=target_asa,
                interval_minutes=interval_minutes,
            )
        else:
            st.error("Line Adherence mode not implemented yet for Volume requirements.")
            return

        data["required_agents"] = req_agents
        data["required_hours"] = req_hours
        st.session_state["data"] = data

        st.markdown("### Required Agents per Interval")
        st.dataframe(req_agents, use_container_width=True)

        st.markdown("### Required Hours per Interval")
        st.dataframe(req_hours, use_container_width=True)

    else:
        st.subheader("Requirement Type: Hours (manual)")

        if data["required_hours"] is None:
            data["required_hours"] = make_empty_week_grid(interval_minutes)

        req_hours = data["required_hours"]

        st.write("Enter required hours per interval for each day.")
        edited_hours = st.data_editor(
            req_hours,
            num_rows="dynamic",
            use_container_width=True,
            key="required_hours_editor",
        )

        data["required_hours"] = edited_hours

        req_agents = edited_hours.copy()
        req_agents = (req_agents / interval_hours).round(2)

        data["required_agents"] = req_agents
        st.session_state["data"] = data

        st.markdown("### Implied Required Agents per Interval")
        st.dataframe(req_agents, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅ Back to Page 4"):
            go_to_page(4)
    with col2:
        if st.button("Next ➜ Page 6 (Roster Counts)"):
            go_to_page(6)


# --- helper: build initial roster counts for Page 6 --- #

def build_initial_roster_counts(interval_minutes: int) -> "pd.DataFrame":
    data = st.session_state["data"]
    agent_types = st.session_state.get("agent_types", [])

    required_agents = data.get("required_agents")
    if required_agents is None:
        return None

    roster = pd.DataFrame(
        0.0,
        index=required_agents.index,
        columns=required_agents.columns,
    )

    interval_labels = list(required_agents.index)
    interval_start_minutes = []
    for label in interval_labels:
        hour, minute = map(int, label.split(":"))
        interval_start_minutes.append(hour * 60 + minute)

    day_labels = list(required_agents.columns)

    for atype in agent_types:
        num_agents = atype["num_agents"]
        if num_agents <= 0:
            continue

        start_time = atype["start_time"]
        end_time = atype["end_time"]
        working_days = atype.get("working_days", day_labels)

        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute

        for d in day_labels:
            if d not in working_days:
                continue
            for idx, label in enumerate(interval_labels):
                t = interval_start_minutes[idx]
                if start_minutes <= end_minutes:
                    in_window = (t >= start_minutes) and (t < end_minutes)
                else:
                    in_window = (t >= start_minutes) or (t < end_minutes)
                if in_window:
                    roster.at[label, d] += num_agents

    roster_capped = roster.where(roster <= required_agents, other=required_agents)
    return roster_capped


# --- Page 6: Roster Counts (Initial) --- #

def page_6():
    st.title("Erlang Simulator Wizard")
    st.header("Page 6: Roster Counts (Initial)")

    config = st.session_state["config"]
    data = st.session_state["data"]
    agent_types = st.session_state.get("agent_types", [])

    interval_minutes = config["interval_minutes"]

    if not agent_types:
        st.error("Please define at least one agent type on Page 4.")
        if st.button("⬅ Back to Page 4"):
            go_to_page(4)
        return

    if data.get("required_agents") is None:
        st.error("Please complete Page 5 to calculate required agents.")
        if st.button("⬅ Back to Page 5"):
            go_to_page(5)
        return

    if data.get("roster_counts_raw") is None:
        roster_counts = build_initial_roster_counts(interval_minutes)
        data["roster_counts_raw"] = roster_counts
        st.session_state["data"] = data
    else:
        roster_counts = data["roster_counts_raw"]

    st.write("This is an initial, simple roster distribution before shrinkage and optimization.")
    st.markdown("### Initial Roster Counts per Interval (All Types Combined)")
    st.dataframe(roster_counts, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅ Back to Page 5"):
            go_to_page(5)
    with col2:
        if st.button("Next ➜ Page 7 (After Out-of-Office Shrinkage)"):
            go_to_page(7)


# --- Page 7: Roster After Out-of-Office Shrinkage --- #

def page_7():
    st.title("Erlang Simulator Wizard")
    st.header("Page 7: Roster After Out-of-Office Shrinkage")

    config = st.session_state["config"]
    data = st.session_state["data"]

    roster_raw = data.get("roster_counts_raw")
    if roster_raw is None:
        st.error("Please complete Page 6 to generate initial roster counts.")
        if st.button("⬅ Back to Page 6"):
            go_to_page(6)
        return

    out_office_pct = config["shrinkage"]["out_office_pct"]

    if data.get("roster_after_ooo") is None:
        roster_after = roster_raw * (1.0 - out_office_pct)
        roster_after = roster_after.round(2)
        data["roster_after_ooo"] = roster_after
        st.session_state["data"] = data
    else:
        roster_after = data["roster_after_ooo"]

    st.write(
        f"Out-of-office shrinkage: {out_office_pct * 100:.1f}% "
        "(leave, training, meetings outside phone time)."
    )  [web:61]
    st.write("Below are the effective in-office roster counts before breaks.")

    st.markdown("### Roster Counts After Out-of-Office Shrinkage")
    st.dataframe(roster_after, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅ Back to Page 6"):
            go_to_page(6)
    with col2:
        if st.button("Next ➜ Page 8 (In-Office Shrinkage / Breaks)"):
            go_to_page(8)


# --- Page 8: Roster After In-Office Shrinkage (Breaks etc.) --- #

def page_8():
    st.title("Erlang Simulator Wizard")
    st.header("Page 8: Roster After In-Office Shrinkage (Breaks)")

    config = st.session_state["config"]
    data = st.session_state["data"]

    roster_after_ooo = data.get("roster_after_ooo")
    if roster_after_ooo is None:
        st.error("Please complete Page 7 first.")
        if st.button("⬅ Back to Page 7"):
            go_to_page(7)
        return

    in_office_pct = config["shrinkage"]["in_office_pct"]

    if data.get("roster_after_all_shrinkage") is None:
        # Apply in-office shrinkage to in-office roster
        # (breaks, coaching, meetings while logged in). [web:61][web:62]
        final_roster = roster_after_ooo * (1.0 - in_office_pct)
        final_roster = final_roster.round(2)
        data["roster_after_all_shrinkage"] = final_roster
        st.session_state["data"] = data
    else:
        final_roster = data["roster_after_all_shrinkage"]

    st.write(
        f"In-office shrinkage: {in_office_pct * 100:.1f}% "
        "(breaks, coaching, short meetings while logged in)."
    )  [web:61]
    st.write("This grid approximates agents actually available to take calls in each interval.")

    st.markdown("### Roster After All Shrinkage (Available for Calls)")
    st.dataframe(final_roster, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅ Back to Page 7"):
            go_to_page(7)
    with col2:
        if st.button("Next ➜ Page 9 (Open Count vs Requirement)"):
            go_to_page(9)


# --- Page 9: Open Count and Over/Under vs Requirement --- #

def page_9():
    st.title("Erlang Simulator Wizard")
    st.header("Page 9: Open Count vs Requirement")

    data = st.session_state["data"]

    required_agents = data.get("required_agents")
    final_roster = data.get("roster_after_all_shrinkage")

    if required_agents is None:
        st.error("Please complete Page 5 to generate required agents.")
        if st.button("⬅ Back to Page 5"):
            go_to_page(5)
        return

    if final_roster is None:
        st.error("Please complete Page 8 to compute available agents after shrinkage.")
        if st.button("⬅ Back to Page 8"):
            go_to_page(8)
        return

    open_count = final_roster.round(2)
    over_under = (open_count - required_agents).round(2)

    data["open_count"] = open_count
    data["over_under"] = over_under
    st.session_state["data"] = data

    st.write("Open Count = agents available after all shrinkage (Page 8).")
    st.write("Over/Under = Open Count − Required Agents (positive = overstaffed, negative = understaffed).")  [web:60][web:69]

    st.markdown("### Open Count (Available Agents)")
    st.dataframe(open_count, use_container_width=True)

    st.markdown("### Over / Under vs Requirement")
    st.dataframe(over_under, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅ Back to Page 8"):
            go_to_page(8)
    with col2:
        if st.button("Next ➜ (Future Pages: Optimization, KPI Simulation)"):
            go_to_page(10)


# --- Main entry point --- #

def main():
    init_wizard_state()
    page = st.session_state["wizard_page"]

    if page == 1:
        page_1()
    elif page == 2:
        page_2()
    elif page == 3:
        page_3()
    elif page == 4:
        page_4()
    elif page == 5:
        page_5()
    elif page == 6:
        page_6()
    elif page == 7:
        page_7()
    elif page == 8:
        page_8()
    elif page == 9:
        page_9()
    else:
        st.write("Later pages not built yet. Go back:")
        if st.button("⬅ Back to Page 1"):
            go_to_page(1)


if __name__ == "__main__":
    main()
