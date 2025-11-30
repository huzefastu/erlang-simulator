# main.py
#
# First version of the wizard: only Page 1 (inputs).
# We store values in st.session_state so later pages can use them.
# Run with: streamlit run main.py

import streamlit as st
import pandas as pd


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
            "kpi_aggregation_level": "interval", # "interval", "day", or "week"
            "kpi_targets": {
                "sla": 0.8,                # 80%
                "service_time_sec": 20,
                "abandon_pct": 0.02,       # 2%
                "abandon_time_sec": 30,
                "asa_sec": 20,
                "interval_target_pct": 0.95,  # for line adherence (later)
                "day_target_pct": 0.95,       # for line adherence (later)
            },
            "shrinkage": {
                "out_office_pct": 0.15,   # 15%
                "in_office_pct": 0.10,    # 10%
            },
        }

    if "data" not in st.session_state:
        st.session_state["data"] = {
        "volume": None, # will be a DataFrame later
        "aht": None, # will be a DataFrame later
        }



def make_empty_week_grid(interval_minutes: int) -> "pd.DataFrame":
    """
    Create an empty week grid with:
    - Rows: time labels like '00:00', '00:15', ...
    - Columns: days Sun–Sat
    """
    intervals_per_day = int(24 * 60 / interval_minutes)
    # Build time labels
    labels = []
    for i in range(intervals_per_day):
        total_minutes = i * interval_minutes
        hour = total_minutes // 60
        minute = total_minutes % 60
        labels.append(f"{hour:02d}:{minute:02d}")  # e.g., "08:30"
    
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    return pd.DataFrame(0.0, index=labels, columns=days)



def go_to_page(page_number: int):
    st.session_state["wizard_page"] = page_number


# --- Page 1: KPI and assumption inputs --- #

def page_1():
    st.title("Erlang Simulator Wizard")
    st.header("Page 1: KPI and Assumption Inputs")

    config = st.session_state["config"]

    # 1a. Interval size
    st.subheader("Interval Size")
    interval_size = st.radio(
        "Choose interval length:",
        options=[15, 30, 60],
        index=[15, 30, 60].index(config["interval_minutes"]),
        horizontal=True,
    )

    # 1b. Requirement type
    st.subheader("Requirement Type")
    requirement_type = st.radio(
        "How do you want to give requirements?",
        options=["volume", "hours"],
        format_func=lambda x: "Volume-based (Erlang) " if x == "volume" else "Hours-based (manual)",
        index=0 if config["requirement_type"] == "volume" else 1,
    )

    # 1c. KPI type
    st.subheader("KPI Type")
    # Note: line_adherence only allowed if requirement_type == "hours"
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

    # 1c. KPI target inputs
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

        # Convert % inputs into 0–1
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

    # 1d + 1e. Shrinkage
    st.subheader("Shrinkage Targets")

    col1, col2 = st.columns(2)
    with col1:
        out_office_pct = st.number_input(
            "Out-of-Office Shrinkage (%)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state["config"]["shrinkage"]["out_office_pct"] * 100,
            step=1.0,
        )
    with col2:
        in_office_pct = st.number_input(
            "In-Office Shrinkage (%)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state["config"]["shrinkage"]["in_office_pct"] * 100,
            step=1.0,
        )

    st.write("These are global shrinkage targets for the whole week.")

    # Save back to session_state
    config["interval_minutes"] = int(interval_size)
    config["requirement_type"] = requirement_type
    config["kpi_type"] = kpi_type
    config["kpi_aggregation_level"] = kpi_aggregation_level
    config["kpi_targets"] = kpi_targets
    config["shrinkage"]["out_office_pct"] = out_office_pct / 100.0
    config["shrinkage"]["in_office_pct"] = in_office_pct / 100.0
    st.session_state["config"] = config

    # Navigation
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

    # If we don't have a volume grid yet, create an empty one
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

    # Save back
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
    
    # If we don't have an AHT grid yet, create an empty one (e.g., 180 seconds default)
    if data["aht"] is None:
        df = make_empty_week_grid(interval_minutes)
        df[:] = 180  # default AHT 180 sec
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
    
    # Save back
    data["aht"] = edited_df
    st.session_state["data"] = data
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅ Back to Page 2"):
            go_to_page(2)
    with col3:
        if st.button("Next ➜ (later pages)"):
            go_to_page(4)  # we will define Page 4 next time


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
    else:
        st.write("Later pages not built yet. Go back:")
        if st.button("⬅ Back to Page 1"):
            go_to_page(1)


if __name__ == "__main__":
    main()
