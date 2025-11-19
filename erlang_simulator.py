import streamlit as st
import pandas as pd
import math
import io

st.title("Contact Center Erlang Simulation")

# 1. SIMULATION MODE FIRST (Main page)
sim_mode = st.radio(
    "Choose simulation mode:",
    [
        "Volume-based Requirement (Erlang)",
        "Hours-based Requirement (coverage)"
    ]
)
st.write(f"**Simulation mode selected:** {sim_mode}")

# ---- SIDEBAR: KPI/ASA and Target Inputs ----
st.sidebar.header("KPI Setup")

# KPI selector (always in sidebar)
kpi_options = [
    "Service Level (SLA)",
    "Abandon Rate",
    "Line Adherence",
    "Average Speed of Answer (ASA)"
]
selected_kpi = st.sidebar.selectbox("KPI for Simulation", kpi_options)

# Target for selected KPI appears in sidebar
if selected_kpi == "Service Level (SLA)":
    target_kpi = st.sidebar.number_input("Target SLA (%)", value=80, min_value=0, max_value=100)
elif selected_kpi == "Abandon Rate":
    target_kpi = st.sidebar.number_input("Max Abandon Rate (%)", value=10, min_value=0, max_value=100)
elif selected_kpi == "Line Adherence":
    target_kpi = st.sidebar.number_input("Target Line Adherence (%)", value=90, min_value=0, max_value=100)
elif selected_kpi == "Average Speed of Answer (ASA)":
    target_kpi = st.sidebar.number_input("Max ASA (seconds)", value=20, min_value=1, max_value=1000)

# Always show ASA target as well (even if not the focus KPI)
asa_target = st.sidebar.number_input("ASA Target (seconds, always active)", value=20, min_value=1, max_value=1000)

# KPI Target Scope input
target_scope = st.sidebar.selectbox(
    "Should KPI be met per:",
    ["Interval", "Day", "Week"]
